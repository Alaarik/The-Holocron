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
        
        # Add force/tech points if any
        # SW5e usually tracks force points / tech points, we could initialize consumables here
        
        
        
        return char
