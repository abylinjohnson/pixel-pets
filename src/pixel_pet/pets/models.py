from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PetAction:
    key: str
    label: str
    asset_path: str
    duration: float
    category: str
    description: str

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class PetProfile:
    key: str
    name: str
    idle_action: str
    actions: tuple[PetAction, ...]

    def to_dict(self):
        return {
            "key": self.key,
            "name": self.name,
            "idle_action": self.idle_action,
            "actions": [action.to_dict() for action in self.actions],
        }
