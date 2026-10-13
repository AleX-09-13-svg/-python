from common.inventor_service_path import ensure_inventor_service_path

ensure_inventor_service_path()

from inventor_service.workflows.analyze_inventor_part import *  # noqa: F401,F403


if __name__ == "__main__":
    main()
