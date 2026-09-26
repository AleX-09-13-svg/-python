import pythoncom
from win32com.client import dynamic


def get_inventor():
    return dynamic.Dispatch(
        pythoncom.GetActiveObject("Inventor.Application").QueryInterface(
            pythoncom.IID_IDispatch
        )
    )
