import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import SchoolSettings
from mobile_api.auth_utils import generate_tokens_for_user
from mobile_api.models import (
    AuditTrailLog,
    SupportTicket,
    SupportTicketMessage,
    UserProfile,
    UserRole,
)


class ManagerSupportApiTests(TestCase):
    def setUp(self):
        self.school_one = SchoolSettings.objects.create(
            school_name='School One', ministry_school_code='S1'
        )
        self.school_two = SchoolSettings.objects.create(
            school_name='School Two', ministry_school_code='S2'
        )
        self.manager_one, self.manager_one_profile = self._user(
            'manager-one', UserRole.MANAGER, self.school_one
        )
        self.manager_two, self.manager_two_profile = self._user(
            'manager-two', UserRole.MANAGER, self.school_two
        )
        self.owner, self.owner_profile = self._user('owner', UserRole.OWNER)
        self.teacher, self.teacher_profile = self._user(
            'teacher', UserRole.TEACHER, self.school_one
        )
        self.parent, self.parent_profile = self._user(
            'parent', UserRole.PARENT, self.school_one
        )

    def _user(self, username, role, school=None):
        user = get_user_model().objects.create_user(username=username, password='test-password')
        profile = UserProfile.objects.create(
            user=user, role=role, school=school, is_approved=True
        )
        return user, profile

    def _auth(self, user, profile):
        token, _ = generate_tokens_for_user(user, profile)
        return {'HTTP_AUTHORIZATION': f'Bearer {token}'}

    def _create_ticket(self):
        response = self.client.post(
            '/api/mobile/manager/support/tickets/create/',
            data=json.dumps({
                'subject': 'Printer problem',
                'description': 'The school printer is unavailable.',
                'category': 'TECHNICAL',
                'priority': 'HIGH',
            }),
            content_type='application/json',
            **self._auth(self.manager_one, self.manager_one_profile),
        )
        self.assertEqual(response.status_code, 201)
        return SupportTicket.objects.get(pk=response.json()['ticket']['id'])

    def test_create_assigns_server_school_and_user_and_audits(self):
        ticket = self._create_ticket()
        self.assertEqual(ticket.school, self.school_one)
        self.assertEqual(ticket.created_by, self.manager_one)
        self.assertTrue(AuditTrailLog.objects.filter(
            action='MANAGER_SUPPORT_TICKET_CREATED', entity_id=str(ticket.id)
        ).exists())

    def test_create_rejects_client_school_or_creator(self):
        response = self.client.post(
            '/api/mobile/manager/support/tickets/create/',
            data=json.dumps({
                'subject': 'Invalid', 'description': 'Invalid ownership attempt',
                'category': 'GENERAL', 'priority': 'MEDIUM',
                'school_id': self.school_two.id, 'created_by': self.manager_two.id,
            }),
            content_type='application/json',
            **self._auth(self.manager_one, self.manager_one_profile),
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SupportTicket.objects.filter(subject='Invalid').exists())

    def test_list_is_filtered_to_manager_school(self):
        own = self._create_ticket()
        other = SupportTicket.objects.create(
            school=self.school_two, created_by=self.manager_two,
            subject='Other school', description='Private', category='GENERAL'
        )
        response = self.client.get(
            '/api/mobile/manager/support/tickets/?status=OPEN&priority=HIGH&category=TECHNICAL&search=Printer',
            **self._auth(self.manager_one, self.manager_one_profile),
        )
        self.assertEqual(response.status_code, 200)
        ids = [row['id'] for row in response.json()['tickets']]
        self.assertIn(own.id, ids)
        self.assertNotIn(other.id, ids)

    def test_cross_school_detail_and_reply_are_forbidden(self):
        other = SupportTicket.objects.create(
            school=self.school_two, created_by=self.manager_two,
            subject='Other school', description='Private'
        )
        auth = self._auth(self.manager_one, self.manager_one_profile)
        detail = self.client.get(
            f'/api/mobile/manager/support/tickets/{other.id}/', **auth
        )
        reply = self.client.post(
            f'/api/mobile/manager/support/tickets/{other.id}/reply/',
            data=json.dumps({'message': 'Not allowed'}), content_type='application/json', **auth
        )
        self.assertEqual(detail.status_code, 403)
        self.assertEqual(reply.status_code, 403)
        self.assertFalse(SupportTicketMessage.objects.filter(ticket=other).exists())

    def test_manager_reply_rejects_internal_note_and_audits_normal_reply(self):
        ticket = self._create_ticket()
        url = f'/api/mobile/manager/support/tickets/{ticket.id}/reply/'
        auth = self._auth(self.manager_one, self.manager_one_profile)
        rejected = self.client.post(
            url, data=json.dumps({'message': 'Hidden', 'is_internal_note': True}),
            content_type='application/json', **auth
        )
        self.assertEqual(rejected.status_code, 400)
        accepted = self.client.post(
            url, data=json.dumps({'message': 'Additional details'}),
            content_type='application/json', **auth
        )
        self.assertEqual(accepted.status_code, 200)
        message = SupportTicketMessage.objects.get(ticket=ticket)
        self.assertFalse(message.is_internal_note)
        self.assertTrue(AuditTrailLog.objects.filter(
            action='MANAGER_SUPPORT_TICKET_REPLIED', entity_id=str(ticket.id)
        ).exists())

    def test_owner_access_reply_update_and_audit_remain_available(self):
        ticket = self._create_ticket()
        auth = self._auth(self.owner, self.owner_profile)
        listing = self.client.get('/api/mobile/owner/support/tickets/', **auth)
        self.assertIn(ticket.id, [row['id'] for row in listing.json()['tickets']])
        reply = self.client.post(
            f'/api/mobile/owner/support/tickets/{ticket.id}/reply/',
            data=json.dumps({'message': 'Owner response'}), content_type='application/json', **auth
        )
        update = self.client.post(
            f'/api/mobile/owner/support/tickets/{ticket.id}/update/',
            data=json.dumps({'status': 'IN_PROGRESS', 'priority': 'URGENT', 'category': 'OPERATIONS'}),
            content_type='application/json', **auth
        )
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(update.status_code, 200)
        self.assertTrue(AuditTrailLog.objects.filter(
            action='OWNER_SUPPORT_TICKET_REPLIED', entity_id=str(ticket.id)
        ).exists())
        self.assertTrue(AuditTrailLog.objects.filter(
            action='OWNER_SUPPORT_TICKET_UPDATED', entity_id=str(ticket.id)
        ).exists())

    def test_teacher_parent_and_unassigned_manager_are_forbidden(self):
        for user, profile in ((self.teacher, self.teacher_profile), (self.parent, self.parent_profile)):
            response = self.client.get(
                '/api/mobile/manager/support/tickets/', **self._auth(user, profile)
            )
            self.assertEqual(response.status_code, 403)
        manager, profile = self._user('manager-without-school', UserRole.MANAGER)
        response = self.client.post(
            '/api/mobile/manager/support/tickets/create/',
            data=json.dumps({'subject': 'No school', 'description': 'No school assigned'}),
            content_type='application/json', **self._auth(manager, profile)
        )
        self.assertEqual(response.status_code, 403)

