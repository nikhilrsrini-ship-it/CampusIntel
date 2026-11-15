from app.database.session import SessionLocal
from app.models import MLModelExperiment
from sqlalchemy.exc import SQLAlchemyError


def record_experiment(name: str, model_name: str, model_version: str, dataset: str, configuration: dict, metrics: dict) -> bool:
    try:
        with SessionLocal() as db:
            db.add(MLModelExperiment(experiment_name=name, model_name=model_name, model_version=model_version, dataset_name=dataset, configuration_json=configuration, metrics_json=metrics))
            db.commit()
        return True
    except SQLAlchemyError:
        return False
