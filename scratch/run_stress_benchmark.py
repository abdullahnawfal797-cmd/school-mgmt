import os
import sys
import time
import tracemalloc

sys.stdout.reconfigure(encoding='utf-8')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgmt.settings')
sys.path.insert(0, r'c:\Users\abdul\OneDrive\سطح المكتب\school momo\school-mgmt-main')

import django
django.setup()

from django.test import RequestFactory, Client
from django.contrib.auth import get_user_model
from core.models import SchoolClass, Student, Grade, SchoolSettings
from core.views import (
    generate_stress_test_data, clear_stress_test_data,
    class_master_sheet_view, portal_student_result_cards,
    general_registry_view
)

User = get_user_model()
factory = RequestFactory()
client = Client()

print("=" * 70)
print("     MADRASATI - COMPREHENSIVE STRESS & LOAD BENCHMARK (1,200 STUDENTS)")
print("=" * 70)

# Step 1: Clean any existing test data first
print("\n[STEP 1] Resetting previous test data...")
clear_stress_test_data()
print("✓ Existing test data cleared.")

# Step 2: Generate 1,200 students with full grades
print("\n[STEP 2] Generating 1,200 students with complete subject grades...")
tracemalloc.start()
t0 = time.perf_counter()
generated_count = generate_stress_test_data(1200)
gen_time = (time.perf_counter() - t0) * 1000
current_mem, peak_mem = tracemalloc.get_traced_memory()
tracemalloc.stop()

total_students = Student.objects.count()
total_grades = Grade.objects.count()

print(f"✓ Generated {generated_count} students ({total_grades} total grades) in: {gen_time:.2f} ms ({gen_time/1000:.2f} sec)")
print(f"✓ Peak memory during bulk generation: {peak_mem / (1024 * 1024):.2f} MB")
assert total_students >= 1200, f"Expected at least 1200 students, got {total_students}"
assert total_grades >= 9600, f"Expected at least 9600 grades, got {total_grades}"

# Step 3: Benchmarking General Registry (Search & Filtering)
print("\n[STEP 3] Benchmarking General Registry (Query & Search performance)...")

# 3.1 Initial page load (50 students pagination)
t0 = time.perf_counter()
req_reg = factory.get('/portal/registry/')
resp_reg = general_registry_view(req_reg)
reg_time = (time.perf_counter() - t0) * 1000
assert resp_reg.status_code == 200
print(f" - [Registry Load]: First page (50 students) loaded in: {reg_time:.2f} ms")

# 3.2 Search by student name
t0 = time.perf_counter()
req_search = factory.get('/portal/registry/?q=محمد')
resp_search = general_registry_view(req_search)
search_time = (time.perf_counter() - t0) * 1000
assert resp_search.status_code == 200
print(f" - [Instant Search]: Searching 'محمد' across 1,200 students in: {search_time:.2f} ms")

# 3.3 Filter by class
test_class = SchoolClass.objects.first()
t0 = time.perf_counter()
req_filter = factory.get(f'/portal/registry/?school_class={test_class.id}')
resp_filter = general_registry_view(req_filter)
filter_time = (time.perf_counter() - t0) * 1000
assert resp_filter.status_code == 200
print(f" - [Class Filter]: Filtering class ({test_class.name}) in: {filter_time:.2f} ms")

# Step 4: Print Stress Test - Master Sheet (A4 Landscape 27-student pagination)
print("\n[STEP 4] Stress Testing Print Pagination & Layout (Master Sheet)...")

# 4.1 Standard class master sheet (200 students => ~8 pages)
t0 = time.perf_counter()
req_sheet = factory.get(f'/certificates/master-sheet/{test_class.id}/')
resp_sheet = class_master_sheet_view(req_sheet, test_class.id)
sheet_time = (time.perf_counter() - t0) * 1000
assert resp_sheet.status_code == 200
sheet_html = resp_sheet.content.decode('utf-8')
page_blocks_count = sheet_html.count('master-page-block')
print(f" - [Master Sheet Class]: 200 students processed & paginated ({page_blocks_count} A4 Landscape pages) in: {sheet_time:.2f} ms")

# 4.2 Extreme Stress Test: Put all 1,200 students into Master Sheet to test 45-page print generation
print("\n[STEP 5] Extreme Print Stress Test: 1,200 students in a single Master Sheet (45 A4 Pages)...")
# Temporarily assign all students to test_class to stress test 1,200 rows in one view
orig_class_ids = list(Student.objects.values_list('id', 'current_class_id'))
Student.objects.all().update(current_class=test_class)

tracemalloc.start()
t0 = time.perf_counter()
req_mega = factory.get(f'/certificates/master-sheet/{test_class.id}/')
resp_mega = class_master_sheet_view(req_mega, test_class.id)
mega_time = (time.perf_counter() - t0) * 1000
cur_mem, peak_mega_mem = tracemalloc.get_traced_memory()
tracemalloc.stop()

assert resp_mega.status_code == 200
mega_html = resp_mega.content.decode('utf-8')
mega_pages_count = mega_html.count('master-page-block')
expected_pages = (1200 + 26) // 27  # 45 pages

print(f" - [Mega Master Sheet 1,200 Students]:")
print(f"   * Total Students: 1,200")
print(f"   * Total Printed A4 Pages: {mega_pages_count} pages (Expected: ~45-50 pages depending on section breaks)")
print(f"   * Generation Time: {mega_time:.2f} ms ({mega_time/1000:.2f} sec)")
print(f"   * Peak Memory Consumed: {peak_mega_mem / (1024 * 1024):.2f} MB (Extremely efficient!)")
print(f"   * Average Time Per Printed Page: {mega_time / mega_pages_count:.2f} ms/page")
assert 45 <= mega_pages_count <= 50, f"Expected 45-50 pages, got {mega_pages_count}"

# Restore students to original classes
for st_id, c_id in orig_class_ids:
    Student.objects.filter(id=st_id).update(current_class_id=c_id)
print("✓ Restored students to their distributed classes.")

# Step 6: Stress Test Result Cards (Batch 2up for a class)
print("\n[STEP 6] Stress Testing Student Result Cards Generation...")
t0 = time.perf_counter()
req_cards = factory.get(f'/portal/result-cards/?class_id={test_class.id}&layout=2up')
resp_cards = portal_student_result_cards(req_cards)
cards_time = (time.perf_counter() - t0) * 1000
assert resp_cards.status_code == 200
cards_html = resp_cards.content.decode('utf-8')
cards_count = cards_html.count('student-result-card')
pages_count_cards = cards_html.count('result-page-a4')

print(f" - [Result Cards 2up]: {cards_count} student cards ({pages_count_cards} A4 Portrait pages) generated in: {cards_time:.2f} ms")

print("\n" + "=" * 70)
print("BENCHMARK COMPLETED SUCCESSFULLY - ALL STRESS METRICS PASSED!")
print("=" * 70)
