from ..models import ContractType
from .base import TailwindModelForm


class ContractTypeForm(TailwindModelForm):
    class Meta:
        model = ContractType
        fields = ["name", "code", "sequence"]
