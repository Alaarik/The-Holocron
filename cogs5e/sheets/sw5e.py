import logging
import re
import aiohttp

from cogs5e.models.errors import ExternalImportError
from cogs5e.models.sheet.base import BaseStats, Saves, Skills
from cogs5e.models.sheet.spellcasting import Spellbook
from cogs5e.models.sheet.resistance import Resistances
from cogs5e.models.character import Character
from gamedata.compendium import compendium

log = logging.getLogger(__name__)

SW5E_URL_RE = re.compile(r"https?://(?:www\.)?sw5e\.com/characters?/([a-zA-Z0-9\-]+)")

class SW5ESheetParser:
    def __init__(self, character_id=None, json_data=None):
        self.character_id = character_id
        self.json_data = json_data
        
    async def get_character(self) -> Character:
        import json
        if self.json_data:
            data = {"jsonData": self.json_data}
        else:
            # fetch json (if they ever add public auth)
            url = f"https://sw5eapi.azurewebsites.net/api/character/{self.character_id}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        raise ExternalImportError("Could not fetch character from SW5e API. Make sure the ID is correct.")
                    data = await resp.json()
            
        if not data.get("jsonData"):
            raise ExternalImportError("Character data is empty or missing from the SW5e API.")
            
        char_data = json.loads(data["jsonData"])
        
        char = Character()
        char.upstream = "sw5e_upload"
        char.name = char_data.get("name", "Unknown Character")
        
        # Calculate level
        level = sum(c.get("levels", 0) for c in char_data.get("classes", []))
        char.levels = level
        
        # Base ability scores (raw)
        base_stats = char_data.get("baseAbilityScores", {})
        char.stats = BaseStats.from_dict({
            "strength": base_stats.get("Strength", 10),
            "dexterity": base_stats.get("Dexterity", 10),
            "constitution": base_stats.get("Constitution", 10),
            "intelligence": base_stats.get("Intelligence", 10),
            "wisdom": base_stats.get("Wisdom", 10),
            "charisma": base_stats.get("Charisma", 10),
        })
        
        # We need to add species bonuses and calculate modifiers properly
        species = char_data.get("species", {})
        improvements = species.get("abilityScoreImprovement", {})
        if improvements:
            for stat_name, val in improvements.items():
                lower_stat = stat_name.lower()
                if hasattr(char.stats, lower_stat):
                    getattr(char.stats, lower_stat).value += val
                    
        # current stats
        current = char_data.get("currentStats", {})
        
        # Very basic AC calculation (10 + dex)
        char.ac = 10 + char.stats.dexterity.modifier
        
        # HP: assume 10 + con for now if not calculated
        char.max_hp = 10 + char.stats.constitution.modifier + (level * 5)
        char.hp = char.max_hp - current.get("hitPointsLost", 0)
        char.temp_hp = current.get("temporaryHitPoints", 0)
        
        char.saves = Saves.from_dict({})
        char.skills = Skills.from_dict({})
        char.resistances = Resistances.from_dict({})
        char.spellbook = Spellbook()
        char.consumables = []
        char.attacks = []
        
        # Parse classes for Powers and Force/Tech Points
        max_force = 0
        max_tech = 0
        for c in char_data.get("classes", []):
            cname = c.get("name", "")
            clevel = c.get("levels", 0)
            arch = c.get("archetype", {}).get("name", "")
            
            # Points Calculation
            if cname == "Consular": max_force += clevel * 4
            elif cname == "Sentinel": max_force += clevel * 3
            elif cname == "Guardian": max_force += clevel * 2
            elif cname == "Engineer": max_tech += clevel * 4
            elif cname == "Scout": max_tech += clevel * 3
            elif cname in ["Fighter", "Monk", "Scholar"] and arch in ["Shield Specialist", "Adept", "Discovery"]:
                pass # 1/3 casting usually gets custom mappings, but omit for simplicity
            
            # Powers
            for p in c.get("forcePowers", []):
                char.spellbook.add_spell(p.lower(), strict=False)
            for p in c.get("techPowers", []):
                char.spellbook.add_spell(p.lower(), strict=False)
                
        # Also parse root custom powers
        for p in char_data.get("customForcePowers", []):
             char.spellbook.add_spell(p.get("name", "").lower(), strict=False)
        for p in char_data.get("customTechPowers", []):
             char.spellbook.add_spell(p.get("name", "").lower(), strict=False)
        
        # Add casting mod to points
        if max_force > 0:
            force_mod = max(char.stats.wisdom.modifier, char.stats.charisma.modifier)
            max_force = max(0, max_force + force_mod)
            from cogs5e.models.sheet.base import Consumable
            char.consumables.append(Consumable.from_dict({
                "name": "Force Points",
                "max": max_force,
                "value": max_force - current.get("forcePointsUsed", 0)
            }))
            
        if max_tech > 0:
            tech_mod = char.stats.intelligence.modifier
            max_tech = max(0, max_tech + tech_mod)
            from cogs5e.models.sheet.base import Consumable
            char.consumables.append(Consumable.from_dict({
                "name": "Tech Points",
                "max": max_tech,
                "value": max_tech - current.get("techPointsUsed", 0)
            }))
            
        return char
