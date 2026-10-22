"""Perfil M2.3B de sondas, NO runner documental ni certificado de seguridad.

No se cargan certificaciones desde JSON, flags, PATH ni variables de entorno.
El futuro adaptador documental debe consumir exclusivamente los bytes obtenidos
bajo TailoringStore._verified_artifact y mantener la revisión/hash del plan.
"""
from dataclasses import asdict, dataclass
import hashlib
import json


@dataclass(frozen=True)
class SyntheticProfile:
    version: str = 'm23b-synthetic-v1'
    output_bytes: int = 1024 * 1024
    address_space_bytes: int = 128 * 1024 * 1024
    file_bytes: int = 2 * 1024 * 1024
    cpu_seconds: int = 2
    wall_seconds: int = 3
    descriptors: int = 64
    processes_per_uid: int = 4096
    namespaces: tuple[str, ...] = ('user', 'pid', 'net', 'ipc', 'uts', 'cgroup')


PROFILE = SyntheticProfile()


def profile_sha256() -> str:
    return hashlib.sha256(json.dumps(asdict(PROFILE), sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class DocumentReadiness:
    profile_sha256: str
    pending: tuple[str, ...]

    @property
    def document_verified(self) -> bool:
        # No adapter implements these controls yet. Synthetic results are never
        # authority to run a document, even if every probe passes.
        return False


def document_readiness() -> DocumentReadiness:
    return DocumentReadiness(profile_sha256(), (
        'document_runner', 'closed_offline_tex_tree', 'aggregate_resources',
        'seccomp_policy', 'document_output_validation', 'm23c_synthetic_documents',
    ))
