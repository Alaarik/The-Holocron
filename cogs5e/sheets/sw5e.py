import logging
import re
import aiohttp
import json
import math

from cogs5e.models.errors import ExternalImportError
from cogs5e.models.sheet.base import BaseStats, Saves, Skills, Levels
from cogs5e.models.sheet.resistance import Resistances
from cogs5e.models.sheet.spellcasting import Spellbook, SpellbookSpell
from cogs5e.models.sheet.attack import AttackList, Attack, old_to_automation
from cogs5e.models.character import Character
from cogs5e.models.sheet.coinpurse import Coinpurse

log = logging.getLogger(__name__)

SW5E_URL_RE = re.compile(r"https?://(?:www\.)?sw5e\.com/characters?/([a-zA-Z0-9\-]+)")

class SW5ESheetParser:
    def __init__(self, character_id=None, json_data=None):
        self.character_id = character_id
        self.json_data = json_data
        self.url = character_id or "json_upload"
        
    async def load_character(self, ctx, args) -> Character:
        if self.json_data:
            data = {"jsonData": self.json_data}
        else:
            url = f"https://sw5eapi.azurewebsites.net/api/character/{self.character_id}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        raise ExternalImportError("Could not fetch character from SW5e API.")
                    data = await resp.json()
            
        if not data.get("jsonData"):
            raise ExternalImportError("Character data is empty or missing.")
            
        char_data = json.loads(data["jsonData"])
        
        # Levels
        level_map = {}
        for c in char_data.get("classes", []):
            level_map[c.get("name", "Unknown")] = c.get("levels", 0)
        levels = Levels(classes=level_map)
        level = sum(level_map.values())
        
        prof_bonus = 2 + ((max(level, 1) - 1) // 4)

        # Build Stats
        base_stats = char_data.get("baseAbilityScores", {})
        stats = BaseStats.from_dict({
            "prof_bonus": prof_bonus,
            "strength": base_stats.get("Strength", 10),
            "dexterity": base_stats.get("Dexterity", 10),
            "constitution": base_stats.get("Constitution", 10),
            "intelligence": base_stats.get("Intelligence", 10),
            "wisdom": base_stats.get("Wisdom", 10),
            "charisma": base_stats.get("Charisma", 10),
        })
        
        improvements = char_data.get("species", {}).get("abilityScoreImprovement", {})
        if improvements:
            for stat_name, val in improvements.items():
                lower_stat = stat_name.lower()
                if hasattr(stats, lower_stat):
                    setattr(stats, lower_stat, getattr(stats, lower_stat) + val)
        
        current = char_data.get("currentStats", {})
        
        ac = 10 + stats.get_mod("dex")
        max_hp = 10 + stats.get_mod("con") + (level * 5)
        hp = max_hp - current.get("hitPointsLost", 0)
        temp_hp = current.get("temporaryHitPoints", 0)
        
        saves = Saves.default(stats)
        skills = Skills.default(stats)
        resistances = Resistances.from_dict({})
        spellbook = Spellbook()
        consumables = []
        attacks_list = []
        coinpurse = Coinpurse()
        
        def get_die_size(lvl):
            if lvl >= 17: return 12
            if lvl >= 13: return 10
            if lvl >= 9: return 8
            if lvl >= 5: return 6
            return 4
            
        max_force = 0
        max_tech = 0
        for c in char_data.get("classes", []):
            cname = c.get("name", "")
            clevel = c.get("levels", 0)
            arch = c.get("archetype", {}).get("name", "")
            
            if cname == "Consular": max_force += clevel * 4
            elif cname == "Sentinel": max_force += clevel * 3
            elif cname == "Guardian": max_force += clevel * 2
            elif cname == "Engineer": max_tech += clevel * 4
            elif cname == "Scout": max_tech += clevel * 3
            elif cname in ["Fighter", "Monk", "Scholar"] and arch in ["Shield Specialist", "Adept", "Discovery"]:
                pass
            
            def add_consumable(name, max_val, reset="long"):
                consumables.append({
                    "name": name,
                    "maxv": max_val,
                    "value": max_val - current.get("featuresTimesUsed", {}).get(name, 0),
                    "reset": reset
                })

            if cname == "Guardian":
                if clevel >= 1:
                    uses = 2
                    if clevel >= 5: uses = 3
                    if clevel >= 9: uses = 4
                    if clevel >= 13: uses = 5
                    if clevel >= 17: uses = 6
                    add_consumable("Channel the Force", uses, "short")
                if clevel >= 2:
                    max_dice = 2
                    if clevel >= 5: max_dice = 3
                    if clevel >= 9: max_dice = 4
                    if clevel >= 13: max_dice = 5
                    if clevel >= 17: max_dice = 6
                    attacks_list.append(Attack("Force-Empowered Strikes", old_to_automation(damage="1d8", details=f"Force-Empowered Strikes additional damage. Maximum limit: {max_dice}d8. (Costs 1 Force Point per d8)")))
                
            elif cname == "Berserker" and clevel >= 1:
                uses = 2
                if clevel >= 3: uses = 3
                if clevel >= 6: uses = 4
                if clevel >= 12: uses = 5
                if clevel >= 17: uses = 6
                if clevel >= 20: uses = 99
                add_consumable("Rage", uses, "long")
                
            elif cname == "Fighter":
                if clevel >= 1: add_consumable("Second Wind", 1, "short")
                if clevel >= 2: add_consumable("Action Surge", 2 if clevel >= 17 else 1, "short")
                if clevel >= 9:
                    uses = 1
                    if clevel >= 13: uses = 2
                    if clevel >= 17: uses = 3
                    add_consumable("Indomitable", uses, "long")
                    
            elif cname == "Monk" and clevel >= 2:
                add_consumable("Focus Points", clevel, "short")
                
            elif cname == "Engineer":
                if clevel >= 1:
                    uses = 2
                    if clevel >= 5: uses = 3
                    if clevel >= 9: uses = 4
                    if clevel >= 13: uses = 5
                    if clevel >= 17: uses = 6
                    add_consumable("Potent Aptitude", uses, "short")
                    die = get_die_size(clevel)
                    attacks_list.append(Attack("Potent Aptitude", old_to_automation(damage=f"1d{die}", details="Potent Aptitude Die")))
                if clevel >= 2:
                    add_consumable("Infuse Item", 1, "long")
                    
            elif cname == "Sentinel":
                if clevel >= 2:
                    uses = 2
                    if clevel >= 9: uses = 3
                    if clevel >= 17: uses = 4
                    add_consumable("Ideal Manifests", uses, "short")
                    die = get_die_size(clevel)
                    attacks_list.append(Attack("Kinetic Combat", old_to_automation(damage=f"1d{die}", details="Kinetic Combat extra damage / effect die")))
                    
            elif cname == "Scholar":
                if clevel >= 1:
                    uses = 3 + ((clevel - 1) // 2)
                    add_consumable("Superiority Dice", uses, "short")
                    die = get_die_size(clevel)
                    attacks_list.append(Attack("Superiority Die", old_to_automation(damage=f"1d{die}", details="Superiority Die Roll")))
                    
            elif cname == "Operative":
                if clevel >= 1:
                    attacks_list.append(Attack("Sneak Attack", old_to_automation(damage=f"{math.ceil(clevel/2)}d6", details="Sneak Attack extra damage.")))
                if clevel >= 3:
                    add_consumable("Bad Feeling", 1, "long")
                    
            elif cname == "Scout":
                if clevel >= 1:
                    die = get_die_size(clevel)
                    attacks_list.append(Attack("Ranger's Quarry", old_to_automation(damage=f"1d{die}", details="Ranger's Quarry extra damage.")))
                
            for p in c.get("forcePowers", []):
                spellbook.spells.append(SpellbookSpell(p.lower(), strict=False))
            for p in c.get("techPowers", []):
                spellbook.spells.append(SpellbookSpell(p.lower(), strict=False))
                
        for p in char_data.get("customForcePowers", []):
            spellbook.spells.append(SpellbookSpell(p.get("name", "").lower(), strict=False))
        for p in char_data.get("customTechPowers", []):
            spellbook.spells.append(SpellbookSpell(p.get("name", "").lower(), strict=False))
    
        if max_force > 0:
            force_mod = max(stats.get_mod("wis"), stats.get_mod("cha"))
            max_force = max(0, max_force + force_mod)
            consumables.append({
                "name": "Force Points",
                "maxv": max_force,
                "value": max_force - current.get("forcePointsUsed", 0)
            })
        
        if max_tech > 0:
            tech_mod = stats.get_mod("int")
            max_tech = max(0, max_tech + tech_mod)
            consumables.append({
                "name": "Tech Points",
                "maxv": max_tech,
                "value": max_tech - current.get("techPointsUsed", 0)
            })
            
        attacks = AttackList(attacks_list)
            
        return Character(
            owner=str(ctx.author.id),
            upstream=f"sw5e_{char_data.get('id') or char_data.get('localId', 'upload')}",
            active=True,
            sheet_type="sw5e",
            import_version=1,
            name=char_data.get("name", "Unknown Character"),
            description="",
            image=char_data.get("image", ""),
            stats=stats,
            levels=levels,
            attacks=attacks,
            skills=skills,
            resistances=resistances,
            saves=saves,
            ac=ac,
            max_hp=max_hp,
            hp=hp,
            temp_hp=temp_hp,
            cvars={},
            overrides={},
            consumables=consumables,
            death_saves={},
            spellbook=spellbook,
            live=None,
            race=char_data.get("species", {}).get("name", ""),
            background=char_data.get("background", {}).get("name", ""),
            coinpurse=coinpurse,
        )
