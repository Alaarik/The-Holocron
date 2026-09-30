from cogs5e.initiative.effects.passive import InitPassiveEffect
from utils.enums import AdvantageType


class TestDodgePassive:
    def test_dodge_passive_is_registered(self):
        assert "attack_advantage_against" in InitPassiveEffect.__effect_attrs__

    def test_dodge_passive_display(self):
        passive = InitPassiveEffect(save_adv={"dex"}, attack_advantage_against=AdvantageType.DIS)
        display = str(passive)
        assert "Attacks Against: Disadvantage" in display
        assert "Save Advantage" in display

    def test_dodge_passive_roundtrip(self):
        passive = InitPassiveEffect(save_adv={"dex"}, attack_advantage_against=AdvantageType.DIS)
        data = passive.to_dict()
        assert data["attack_advantage_against"] == AdvantageType.DIS.value
        assert data["save_adv"] == ["dex"]
        restored = InitPassiveEffect.from_dict(data)
        assert restored.attack_advantage_against == AdvantageType.DIS
        assert restored.save_adv == {"dex"}

    def test_dodge_passive_omitted_by_default(self):
        # effects created before this passive existed (or without it) are unaffected
        assert "attack_advantage_against" not in InitPassiveEffect().to_dict()
        assert "attack_advantage_against" not in InitPassiveEffect.from_dict({}).to_dict()
