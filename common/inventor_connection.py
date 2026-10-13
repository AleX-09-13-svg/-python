from common.inventor_service_path import ensure_inventor_service_path

ensure_inventor_service_path()

from inventor_service import Inventor


def _connection_error(exc):
    error = RuntimeError(
        "Cannot connect to Autodesk Inventor through COM. "
        "Make sure Inventor is fully started, no modal dialog is open, "
        "and Python is running with the same administrator rights as Inventor."
    )
    error.__cause__ = exc
    return error


def get_inventor():
    try:
        return Inventor.get_application()
    except Exception:
        import win32com.client

        try:
            app = win32com.client.Dispatch("Inventor.Application")
            app.Visible = True
            return app
        except Exception as exc:
            raise _connection_error(exc)


def get_inventor_service():
    try:
        return Inventor()
    except Exception:
        return Inventor(app=get_inventor())
