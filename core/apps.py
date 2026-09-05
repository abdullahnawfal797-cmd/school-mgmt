from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        import sys
        # Avoid running in management commands like migrate, makemigrations, check
        if any(cmd in sys.argv for cmd in ['makemigrations', 'migrate', 'check', 'test', 'shell']):
            return
        try:
            import threading
            from .backup_vault import create_daily_backup_snapshot
            from .cloud_sync import upload_cloud_backup_async

            def startup_tasks():
                create_daily_backup_snapshot()
                try:
                    import time
                    time.sleep(2)
                    upload_cloud_backup_async()
                except Exception:
                    pass

            threading.Thread(target=startup_tasks, daemon=True, name="StartupDailyTasks").start()
        except Exception:
            pass
