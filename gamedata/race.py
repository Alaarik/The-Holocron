from .mixins import DescribableMixin, LimitedUseGrantorMixin
from .shared import Sourced


class Race(Sourced):
    entity_type = "race"
    type_id = 1743923279

    def __init__(self, name, size, speed, traits, **kwargs):
        """
        :type name: str
        :type size: str
        :type speed: str
        :type traits: list[RaceFeature]
        """
        super().__init__(False, **kwargs)
        self.name = name
        self.size = size
        self.speed = speed
        self.traits = traits

    @classmethod
    def from_data(cls, d):
        inst = cls(
            d.get("name", "Unknown Species"),
            d.get("size", "Medium"),
            "30", # Speed often in traits, assume 30
            traits=[],
            source=d.get("contentSource", "PHB"),
            entity_id=d.get("name"),
            page=0,
            url="",
            is_free=True,
            is_legacy=False,
        )
        if "traits" in d:
            inst.traits = [RaceFeature.from_data(t, inst) for t in d["traits"]]
        return inst

class SubRace(Race):
    entity_type = "subrace"
    type_id = 1228963568


class RaceFeature(LimitedUseGrantorMixin, DescribableMixin, Sourced):
    entity_type = "race-feature"
    type_id = 1960452172

    def __init__(self, name, text, options, inherited=False, **kwargs):
        super().__init__(homebrew=False, **kwargs)
        self.name = name
        self.text = text
        self.options = options
        self.inherited = inherited

    @classmethod
    def from_data(cls, d, source_race, **kwargs):
        inst = cls(
            d.get("name", "Unknown Feature"),
            d.get("description", ""),
            options=[],
            inherited=False,
            entity_id=d.get("name"),
            page=0,
            source=source_race.source,
            is_free=source_race.is_free,
            is_legacy=source_race.is_legacy,
            url=source_race.raw_url,
            entitlement_entity_id=source_race.entity_id,
            entitlement_entity_type=source_race.entity_type,
            **kwargs,
        )
        # sw5e doesn't have options natively inside traits yet
        inst.initialize_limited_use(d)
        return inst

    @property
    def description(self):
        return self.text


class RaceFeatureOption(LimitedUseGrantorMixin, Sourced):
    entity_type = "race-feature-option"
    type_id = 306912077

    def __init__(self, name, **kwargs):
        super().__init__(homebrew=False, **kwargs)
        self.name = name

    @classmethod
    def from_race_feature(cls, d, race_feature: RaceFeature, **kwargs):
        return cls(
            f"{race_feature.name} ({d['name']})",
            entity_id=d["id"],
            page=race_feature.page,
            source=race_feature.source,
            is_free=race_feature.is_free,
            is_legacy=race_feature.is_legacy,
            url=race_feature.raw_url,
            entitlement_entity_id=race_feature.entitlement_entity_id,
            entitlement_entity_type=race_feature.entitlement_entity_type,
            parent=race_feature,
            **kwargs,
        ).initialize_limited_use(d)
