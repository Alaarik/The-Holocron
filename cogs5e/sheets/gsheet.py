"""
Created on May 8, 2017

@author: andrew
"""

import asyncio
import datetime
import json
import logging
import re
import aiohttp
import openpyxl
from io import BytesIO
from contextlib import contextmanager
from urllib.parse import urlparse

import google.oauth2.service_account
import gspread
from d20 import RollSyntaxError
from google.oauth2.service_account import Credentials
from gspread import SpreadsheetNotFound
from gspread.exceptions import APIError, WorksheetNotFound
from gspread.utils import a1_to_rowcol, fill_gaps
from cogs5e.models.sheet.coinpurse import Coinpurse

from cogs5e.models.character import Character
from cogs5e.models.errors import ExternalImportError
from cogs5e.models.sheet.action import Actions
from cogs5e.models.sheet.attack import Attack, AttackList
from cogs5e.models.sheet.base import BaseStats, Levels, Saves, Skill, Skills
from cogs5e.models.sheet.resistance import Resistances
from cogs5e.models.sheet.spellcasting import Spellbook, SpellbookSpell
from cogs5e.sheets.abc import SHEET_VERSION, SheetLoaderABC
from cogs5e.sheets.errors import MissingAttribute, AttackSyntaxError, InvalidImageURL, InvalidCoin
from cogs5e.sheets.utils import get_actions_for_names
from gamedata.compendium import compendium
from utils import config
from utils.constants import DAMAGE_TYPES, COIN_TYPES
from utils.dice import get_roll_comment
from utils.functions import search

log = logging.getLogger(__name__)

POS_RE = re.compile(r"([A-Z]+)(\d+)")
IGNORED_SPELL_VALUES = {
    "MAX",
    "SLOTS",
    "CANTRIPS",
    "1ST LEVEL",
    "2ND LEVEL",
    "3RD LEVEL",
    "4TH LEVEL",
    "5TH LEVEL",
    "6TH LEVEL",
    "7TH LEVEL",
    "8TH LEVEL",
    "9TH LEVEL",
    "\u25c9",
    "\u25cd",
    "You can hide each level of spells individually by hiding the rows (on the left).",
}
SPELL_RANGES = [  # list of (col, prep col, rownums)
    # cantrips
    ("N", None, range(96, 99)),
    ("X", None, range(96, 99)),
    ("AH", None, range(96, 99)),
    # level 1
    ("D", "C", range(100, 105)),
    ("N", "M", range(100, 105)),
    ("X", "W", range(100, 105)),
    # level 2
    ("N", "M", range(106, 111)),
    ("X", "W", range(106, 111)),
    ("AH", "AG", range(106, 111)),
    # level 3
    ("D", "C", range(112, 117)),
    ("N", "M", range(112, 117)),
    ("X", "W", range(112, 117)),
    # level 4
    ("N", "M", range(118, 122)),
    ("X", "W", range(118, 122)),
    ("AH", "AG", range(118, 122)),
    # level 5
    ("D", "C", range(123, 127)),
    ("N", "M", range(123, 127)),
    ("X", "W", range(123, 127)),
    # level 6
    ("N", "M", range(128, 132)),
    ("X", "W", range(128, 132)),
    ("AH", "AG", range(128, 132)),
    # level 7
    ("D", "C", range(133, 136)),
    ("N", "M", range(133, 136)),
    ("X", "W", range(133, 136)),
    # level 8
    ("N", "M", range(137, 140)),
    ("X", "W", range(137, 140)),
    ("AH", "AG", range(137, 140)),
    # level 9
    ("D", "C", range(141, 144)),
    ("N", "M", range(141, 144)),
    ("X", "W", range(141, 144)),
]
SPELL_RANGES_ADDITIONAL = [
    # cantrips
    ("N", None, range(17, 20)),
    ("X", None, range(17, 20)),
    ("AH", None, range(17, 20)),
    # level 1
    ("D", "C", range(21, 26)),
    ("N", "M", range(21, 26)),
    ("X", "W", range(21, 26)),
    # level 2
    ("N", "M", range(27, 32)),
    ("X", "W", range(27, 32)),
    ("AH", "AG", range(27, 32)),
    # level 3
    ("D", "C", range(33, 38)),
    ("N", "M", range(33, 38)),
    ("X", "W", range(33, 38)),
    # level 4
    ("N", "M", range(39, 43)),
    ("X", "W", range(39, 43)),
    ("AH", "AG", range(39, 43)),
    # level 5
    ("D", "C", range(44, 48)),
    ("N", "M", range(44, 48)),
    ("X", "W", range(44, 48)),
    # level 6
    ("N", "M", range(49, 53)),
    ("X", "W", range(49, 53)),
    ("AH", "AG", range(49, 53)),
    # level 7
    ("D", "C", range(54, 57)),
    ("N", "M", range(54, 57)),
    ("X", "W", range(54, 57)),
    # level 8
    ("N", "M", range(58, 61)),
    ("X", "W", range(58, 61)),
    ("AH", "AG", range(58, 61)),
    # level 9
    ("D", "C", range(62, 65)),
    ("N", "M", range(62, 65)),
    ("X", "W", range(62, 65)),
]
BASE_ABILITY_CHECKS = (  # list of (MOD_CELL/ROW, SKILL_NAME, ADV_CELL)
    ("C13", "strength", None),
    ("C18", "dexterity", None),
    ("C23", "constitution", None),
    ("C33", "wisdom", None),
    ("C28", "intelligence", None),
    ("C38", "charisma", None),
)
SKILL_CELL_MAP = (  # list of (MOD_CELL/ROW, SKILL_NAME, ADV_CELL)
    (25, "acrobatics", None),
    (26, "animalHandling", None),
    (27, "technology", None),
    (28, "athletics", None),
    (22, "charismaSave", None),
    (19, "constitutionSave", None),
    (29, "deception", None),
    (18, "dexteritySave", None),
    (30, "lore", None),
    ("V12", "initiative", "V11"),
    (31, "insight", None),
    (20, "intelligenceSave", None),
    (32, "intimidation", None),
    (33, "investigation", None),
    (34, "medicine", None),
    (35, "nature", None),
    (36, "perception", None),
    (37, "performance", None),
    (38, "persuasion", None),
    (39, "piloting", None),
    (40, "sleightOfHand", None),
    (41, "stealth", None),
    (17, "strengthSave", None),
    (42, "survival", None),
    (21, "wisdomSave", None),
)
RESIST_COLS = (
    ("resist", "T"),  # T69:T79, 1.4/2.x
    ("immune", "AE"),  # AE69:AE79, 1.4/2.0
    ("immune", "AB"),  # AB69:AB79, 2.1 only
    ("vuln", "AI"),
)  # AI69:AI79, 2.1 only
SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

URL_KEY_V1_RE = re.compile(r"key=([^&#]+)")
URL_KEY_V2_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")


def extract_gsheet_id_from_url(url):
    m2 = URL_KEY_V2_RE.search(url)
    if m2:
        return m2.group(1)
    m1 = URL_KEY_V1_RE.search(url)
    if m1:
        return m1.group(1)
    raise ExternalImportError("This is not a valid Google Sheets link.")


def letter2num(letters, zbase=True):
    """A = 1, C = 3 and so on. Convert spreadsheet style column
    enumeration to a number.
    """

    letters = letters.upper()
    res = 0
    weight = len(letters) - 1
    for i, ch in enumerate(letters):
        res += (ord(ch) - 64) * 26 ** (weight - i)
    if not zbase:
        return res
    return res - 1


class TempCharacter:
    def __init__(self, worksheet):
        self.worksheet = worksheet
        self.values = self._get_all_values()
        self.unformatted_values = self.values
        
    def _get_all_values(self):
        max_row = self.worksheet.max_row
        max_col = self.worksheet.max_column
        grid = []
        for r in range(1, max_row + 1):
            row_data = []
            for c in range(1, max_col + 1):
                val = self.worksheet.cell(row=r, column=c).value
                if val is None:
                    row_data.append("")
                else:
                    row_data.append(str(val))
            grid.append(row_data)
        return grid

    def _get_value(self, source, pos):
        _pos = POS_RE.match(pos)
        if _pos is None:
            raise ValueError("No A1-style position found.")
        col = letter2num(_pos.group(1))
        row = int(_pos.group(2)) - 1
        
        if row >= len(source) or col >= len(source[row]):
            return ""
            
        value = source[row][col]
        return value

    def value(self, pos):
        return self._get_value(self.values, pos)

    def unformatted_value(self, pos):
        return self._get_value(self.unformatted_values, pos)

    def value_range(self, rng):
        start, end = rng.split(":")
        (row_offset, column_offset) = a1_to_rowcol(start)
        (last_row, last_column) = a1_to_rowcol(end)

        out = []
        for row in self.values[row_offset - 1 : last_row]:
            # pad row if necessary
            if len(row) < last_column:
                row = row + [""] * (last_column - len(row))
            out.extend(row[column_offset - 1 : last_column])
        return out


class GoogleSheet(SheetLoaderABC):
    def __init__(self, url):
        super(GoogleSheet, self).__init__(url)
        self.args = None
        self.additional = None
        self.version = (1, 0)  # major, minor

        self.total_level = 0

        # cache
        self._stats = None

    async def get_character(self):
        return await self._gchar()

    async def _gchar(self):
        export_url = f"https://docs.google.com/spreadsheets/d/{self.url}/export?format=xlsx"
        async with aiohttp.ClientSession() as session:
            async with session.get(export_url) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise ExternalImportError(f"Failed to download Google Sheet (HTTP {resp.status}). Ensure it is shared to 'Anyone with the link can view'.")
                data = await resp.read()
                
        try:
            wb = openpyxl.load_workbook(BytesIO(data), data_only=True)
        except Exception:
            raise ExternalImportError("Failed to parse Google Sheet. Ensure it is a valid Google Sheet.")
            
        self.character_data = TempCharacter(wb.worksheets[0])
        vcell = self.character_data.value("AQ4")
        if "1.3" in vcell:
            self.version = (1, 3)
        elif vcell:
            additional_sheet = next((ws for ws in wb.worksheets if ws.title == "Additional"), None)
            if additional_sheet:
                self.additional = TempCharacter(additional_sheet)
            else:
                self.additional = None
                
            self.version = (2, 1) if "2.1" in vcell else (2, 0) if "2" in vcell else (1, 0)
            
            if self.version >= (2, 1):
                inventory_sheet = next((ws for ws in wb.worksheets if ws.title == "Inventory"), None)
                if inventory_sheet:
                    self.inventory = TempCharacter(inventory_sheet)
                else:
                    self.inventory = None
        
        return self

    # main loading methods
    async def load_character(self, ctx, args):
        self.args = args
        owner_id = str(ctx.author.id)
        
        await self.get_character()
        
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(None, self._load_character, owner_id, args)

    def _load_character(self, owner_id: str, args):
        upstream = f"google-{self.url}"
        active = False
        sheet_type = "google"
        import_version = SHEET_VERSION
        name = self.character_data.value("C6").strip() or "Unnamed"
        description = self.get_description()
        image = self.get_image()

        stats = self.get_stats()
        levels = self.get_levels()
        attacks = self.get_attacks()

        coinpurse = self.get_coinpurse()

        skills, saves = self.get_skills_and_saves()

        resistances = self.get_resistances()
        ac = self.get_ac()
        max_hp = self.get_hp()
        hp = max_hp
        temp_hp = 0

        cvars = {}
        overrides = {}
        death_saves = {}
        consumables = []
        
        # SW5e: Add Force Points, Tech Points, Channel the Force
        max_force = 0
        max_tech = 0
        
        normalized_classes = {}
        for cname, clevel in levels.classes.items():
            base_cname = cname.title().replace("light", "").replace("Light", "").replace("dark", "").replace("Dark", "").strip()
            normalized_classes[base_cname] = clevel
            
        for cname, clevel in normalized_classes.items():
            if cname == "Consular": max_force += clevel * 4
            if cname == "Guardian": max_force += clevel * 2
            if cname == "Sentinel": max_force += clevel * 3
            if cname == "Engineer": max_tech += clevel * 2
            if cname == "Scout": max_tech += clevel * 1
            
            if cname in ["Guardian", "Consular"] and clevel >= 3:
                uses = 2
                if clevel >= 5: uses = 3
                if clevel >= 9: uses = 4
                if clevel >= 13: uses = 5
                if clevel >= 17: uses = 6
                consumables.append({
                    "name": "Channel the Force",
                    "maxv": uses,
                    "value": uses,
                    "reset": "short"
                })
                


        if max_force > 0:
            force_mod = max(stats.get_mod("wis"), stats.get_mod("cha"))
            max_force = max(0, max_force + force_mod)
            consumables.append({
                "name": "Force Points",
                "maxv": max_force,
                "value": max_force
            })
            
        if max_tech > 0:
            tech_mod = stats.get_mod("int")
            max_tech = max(0, max_tech + tech_mod)
            consumables.append({
                "name": "Tech Points",
                "maxv": max_tech,
                "value": max_tech
            })
            
        # Hit Dice Generation
        for cname, clevel in normalized_classes.items():
            hit_die_size = 8 # default
            if cname.title() in ["Berserker"]: hit_die_size = 12
            elif cname.title() in ["Fighter", "Guardian", "Scout"]: hit_die_size = 10
            elif cname.title() in ["Engineer", "Consular", "Scholar", "Operative", "Monk", "Sentinel"]: hit_die_size = 8
            
            consumables.append({
                "name": f"Hit Dice (d{hit_die_size})",
                "maxv": clevel,
                "value": clevel,
                "reset": "long"
            })

        spellbook = self.get_spellbook()
        live = None
        race = self.get_race()
        background = self.get_background()
        actions = self.get_actions()
        
        # Determine Reliable Vigor uses safely by checking if they actually have the feature
        has_vigor = False
        for a in actions.actions:
            if a.name == "Reliable Vigor":
                has_vigor = True
                
        if has_vigor:
            clevel = normalized_classes.get("Guardian", 0)
            uses = 3
            if clevel >= 9: uses = 4
            if clevel >= 13: uses = 5
            if clevel >= 17: uses = 6
            consumables.append({
                "name": "Reliable Vigor",
                "maxv": uses,
                "value": uses,
                "reset": "long"
            })

        character = Character(
            owner_id,
            upstream,
            active,
            sheet_type,
            import_version,
            name,
            description,
            image,
            stats,
            levels,
            attacks,
            skills,
            resistances,
            saves,
            ac,
            max_hp,
            hp,
            temp_hp,
            cvars,
            overrides,
            consumables,
            death_saves,
            spellbook,
            live,
            race,
            background,
            actions=actions,
            coinpurse=coinpurse,
        )
        return character

    # calculator functions
    def get_description(self):
        if self.character_data is None:
            raise Exception("You must call get_character() first.")
        character = self.character_data
        g = character.value("C150").lower()
        n = character.value("C6")
        pronoun = "She" if g == "female" else "He" if g == "male" else "They"
        verb1 = "is" if pronoun != "They" else "are"
        verb2 = "has" if pronoun != "They" else "have"
        desc = (
            "{0} is a level {1} {2} {3}. {4} {11} {5} years old, {6} tall, and appears to weigh about {7}. "
            "{4} {12} {8} eyes, {9} hair, and {10} skin."
        )
        desc = desc.format(
            n,
            character.value("AL6"),
            character.value("T7"),
            character.value("T5"),
            pronoun,
            character.value("C148") or "unknown",
            character.value("F148") or "unknown",
            character.value("I148") or "unknown",
            character.value("F150").lower() or "unknown",
            character.value("I150").lower() or "unknown",
            character.value("L150").lower() or "unknown",
            verb1,
            verb2,
        )
        return desc

    def get_stats(self):
        """Returns a dict of stats."""
        if self.character_data is None:
            raise Exception("You must call get_character() first.")
        character = self.character_data
        if self._stats is not None:
            return self._stats
        try:
            prof_bonus = int(character.value("H14"))
        except (TypeError, ValueError):
            raise MissingAttribute("Proficiency Bonus", "H14", character.worksheet.title)
        index = 15
        stat_dict = {}
        for stat in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"):
            try:
                stat_dict[stat] = int(character.value("C" + str(index)))
                index += 5
            except (TypeError, ValueError):
                raise MissingAttribute(stat, "C" + str(index), character.worksheet.title)
        stats = BaseStats(prof_bonus=prof_bonus, **stat_dict)
        self._stats = stats
        return stats

    def get_coinpurse(self):
        if self.character_data is None:
            raise Exception("You must call get_character() first.")
        coins = {}

        for c_type in COIN_TYPES:
            if self.version >= (2, 1):
                if not self.inventory:  # If they renamed the sheet or deleted it
                    coin_value = 0
                else:
                    coin_value = self.inventory.unformatted_value(COIN_TYPES[c_type]["gSheet"]["v2"]) or 0
            else:
                coin_value = self.character_data.unformatted_value(COIN_TYPES[c_type]["gSheet"]["v14"]) or 0
            try:
                coins[c_type] = int(coin_value)
            except ValueError as e:
                if self.version >= (2, 1):
                    cell = COIN_TYPES[c_type]["gSheet"]["v2"]
                    sheet = "Inventory"
                else:
                    cell = COIN_TYPES[c_type]["gSheet"]["v14"]
                    sheet = self.character_data.worksheet.title
                raise InvalidCoin(cell, sheet, COIN_TYPES[c_type]["name"], e)
        return Coinpurse(pp=coins["pp"], gp=coins["gp"], ep=coins["ep"], sp=coins["sp"], cp=coins["cp"])

    def get_levels(self):
        if self.character_data is None:
            raise Exception("You must call get_character() first.")
        try:
            total_level = int(self.character_data.value("AL6"))
            self.total_level = total_level
        except ValueError:
            raise MissingAttribute("Character level", "AL5", self.character_data.worksheet.title)
        level_dict = {}
        if self.additional:
            for rownum in range(69, 79):  # sheet2, C69:C78
                namecell = f"C{rownum}"
                levelcell = f"N{rownum}"
                classname = self.additional.value(namecell)
                if classname:
                    classname = re.sub(r"[.$]", "_", classname)  # sentry-H7 - invalid class names
                    classlevel = int(self.additional.value(levelcell))
                    level_dict[classname] = classlevel
                else:  # classes should be top-aligned
                    break
        
        # SW5e Fallback: Parse T5 if additional sheet is missing or empty
        if not level_dict:
            try:
                class_str = str(self.character_data.value("T5") or "")
                # E.g. "Shien/Djem So Formn GuardianLight 10" or "Fighter 2 / Guardian 8"
                matches = re.findall(r'([A-Za-z\s/]+?)\s+(\d+)', class_str)
                for name, lvl in matches:
                    for c in ["Guardian", "Consular", "Sentinel", "Fighter", "Operative", "Scholar", "Monk", "Scout", "Engineer", "Berserker"]:
                        if c.lower() in name.lower():
                            level_dict[c] = int(lvl)
            except:
                pass

        levels = Levels(level_dict, total_level)
        return levels

    def get_attacks(self):
        """Returns an attack list."""
        if self.character_data is None:
            raise Exception("You must call get_character() first.")
        attacks = AttackList()
        for rownum in range(32, 37):  # sht1, R32:R36
            a = self.parse_attack(f"R{rownum}", f"Y{rownum}", f"AC{rownum}")
            if a is not None:
                attacks.append(a)
        if self.additional:
            for rownum in range(3, 14):  # sht2, B3:B13; W3:W13
                additional = self.parse_attack(f"B{rownum}", f"I{rownum}", f"M{rownum}", self.additional)
                other = self.parse_attack(f"W{rownum}", f"AD{rownum}", f"AH{rownum}", self.additional)
                if additional is not None:
                    attacks.append(additional)
                if other is not None:
                    attacks.append(other)
        return attacks

    def get_skills_and_saves(self):
        if self.character_data is None:
            raise Exception("You must call get_character() first.")
        character = self.character_data
        skills = {}
        saves = {}
        is_joat = False
        is_ra = False
        all_check_bonus = 0

        if self.version == (2, 0):
            is_joat = bool(character.value("AR45"))
            all_check_bonus = int(character.value("AQ26") or 0)
        elif self.version == (2, 1):
            is_joat = bool(character.value("AQ59"))
            is_ra = bool(character.value("AQ67"))  # parsing for remarkable athlethe from champion 7
            all_check_bonus = int(character.value("AR58"))
        joat_bonus = int(is_joat and self.get_stats().prof_bonus // 2)
        # upside-down floor division to do ceiling division for half-prof bonus (rounded up) of remarkable athlethe
        ra_bonus = int(is_ra and -(self.get_stats().prof_bonus // -2))

        # calculate str, dex, con, etc checks
        for cell, skill, advcell in BASE_ABILITY_CHECKS:
            try:
                # add bonuses manually since the cell does not include them
                # seperate basic abilities into (dex, str, con) so remarkable athlete half-prof can be added
                if skill == "dexterity" or skill == "constitution" or skill == "strength":
                    value = int(character.value(cell)) + all_check_bonus + max(joat_bonus, ra_bonus)
                else:
                    value = int(character.value(cell)) + all_check_bonus + joat_bonus
            except (TypeError, ValueError):
                raise MissingAttribute(skill, cell, character.worksheet.title)
            prof = 0
            if is_ra:
                if skill == "dexterity" or skill == "constitution" or skill == "strength":
                    prof = 0.5
            if is_joat:
                prof = 0.5
            skl_obj = Skill(value, prof)
            skills[skill] = skl_obj
        # read the value of the rest of the skills
        for cell, skill, advcell in SKILL_CELL_MAP:
            if isinstance(cell, int):
                advcell = f"F{cell}"
                profcell = f"H{cell}"
                cell = f"I{cell}"
            else:
                profcell = None
            try:
                value = int(character.value(cell))
            except (TypeError, ValueError):
                raise MissingAttribute(skill, cell, character.worksheet.title)
            adv = None
            if self.version >= (2, 0) and advcell:
                advtype = character.unformatted_value(advcell)
                if isinstance(advtype, str):
                    advtype = advtype.lower()
                if advtype in {"a", "adv", "advantage"}:
                    adv = True
                elif advtype in {"d", "dis", "disadvantage"}:
                    adv = False
            prof = 0
            if "Save" not in skill and is_joat:
                prof = 0.5
            if profcell:
                proftype = character.unformatted_value(profcell)
                if isinstance(proftype, str):
                    proftype = proftype.lower()
                if proftype == "e":
                    prof = 2
                elif proftype and proftype != "0":
                    prof = 1
            skl_obj = Skill(value, prof, adv=adv)
            if "Save" in skill:
                saves[skill] = skl_obj
            else:
                skills[skill] = skl_obj
        skills = Skills(skills)
        saves = Saves(saves)
        return skills, saves

    def get_resistances(self):
        out = {"resist": [], "immune": [], "vuln": []}
        if not self.additional:  # requires 2.0
            return Resistances.from_dict(out)
        for rownum in range(69, 80):
            for resist_type, col in RESIST_COLS:
                try:
                    dtype = self.additional.value(f"{col}{rownum}")
                except IndexError:
                    dtype = None
                if dtype:
                    out[resist_type].append(dtype.lower())
        return Resistances.from_dict(out)

    def get_ac(self):
        try:
            return int(self.character_data.value("R12"))
        except (TypeError, ValueError):
            raise MissingAttribute("AC", "R12", self.character_data.worksheet.title)

    def get_hp(self):
        try:
            return int(self.character_data.unformatted_value("U16"))
        except (TypeError, ValueError):
            raise MissingAttribute("Max HP", "U16", self.character_data.worksheet.title)

    def get_race(self):
        return self.character_data.value("T7").strip()

    def get_background(self):
        if self.version >= (2, 0):
            return self.character_data.value("AJ11").strip()
        return self.character_data.value("Z5").strip()

    def get_image(self):
        image = self.character_data.value("C176").strip()
        if image:
            try:
                result = urlparse(image)
                if not all([result.scheme, result.netloc]):
                    raise InvalidImageURL(self.character_data.worksheet.title, f"Invalid URL: {image}")
                return image
            except ValueError as e:
                raise InvalidImageURL(self.character_data.worksheet.title, e)
        return None

    def get_spellbook(self):
        if self.character_data is None:
            raise Exception("You must call get_character() first.")
        # max slots
        slots = {
            "1": int(self.character_data.value("AK101") or 0),
            "2": int(self.character_data.value("E107") or 0),
            "3": int(self.character_data.value("AK113") or 0),
            "4": int(self.character_data.value("E119") or 0),
            "5": int(self.character_data.value("AK124") or 0),
            "6": int(self.character_data.value("E129") or 0),
            "7": int(self.character_data.value("AK134") or 0),
            "8": int(self.character_data.value("E138") or 0),
            "9": int(self.character_data.value("AK142") or 0),
        }

        potential_spells = self._get_potential_spells()

        spells = []
        for spell_name, prepared in potential_spells:
            spell_name = spell_name.strip()
            if len(spell_name) > 2 and spell_name not in IGNORED_SPELL_VALUES:
                log.debug(f"Searching for spell {spell_name}")
                result, strict = search(compendium.spells, spell_name, lambda sp: sp.name, strict=True)
                if result and strict:
                    spells.append(SpellbookSpell(result.name, True, prepared=prepared))
                else:
                    spells.append(SpellbookSpell(spell_name.strip(), prepared=prepared))
        # dc
        try:
            dc = int(self.character_data.value("AB91") or 0)
        except ValueError:
            dc = None
        # sab
        try:
            sab = int(self.character_data.value("AI91") or 0)
        except ValueError:
            sab = None
        # spellcasting mod
        spell_mod_value = self.character_data.value("U91")
        spell_mod = None
        if spell_mod_value:  # it might be in the form of a ability name, or an int, wjdk
            try:
                spell_mod = self.get_stats().get_mod(spell_mod_value)
            except ValueError:
                try:
                    spell_mod = int(spell_mod_value)
                except (TypeError, ValueError):
                    spell_mod = None
        spellbook = Spellbook(slots, slots, spells, dc, sab, self.total_level, spell_mod)
        return spellbook

    def get_actions(self):
        # v1: Z45:AH56
        # v2: C59:AC84
        if self.version >= (2, 0):
            feature_names = self.character_data.value_range("C59:AC84")
        else:
            feature_names = self.character_data.value_range("Z45:AH56")
        actions = get_actions_for_names(feature_names)
        
        # SW5e bypass: add unrecognised features as dummy actions
        found_names = {a.name.lower() for a in actions}
        from cogs5e.models.sheet.action import Action
        for f in feature_names:
            if not f or f.lower() in found_names or f.lower().strip() == "read me": continue
            actions.append(Action(name=f, uid=None, id=0, type_id=0, activation_type=None))
            
        return Actions(actions)

    # helper methods
    def parse_attack(self, name_index, bonus_index, damage_index, sheet=None):
        """Calculates and returns a dict."""
        if self.character_data is None:
            raise Exception("You must call get_character() first.")

        wksht = sheet or self.character_data

        name = wksht.value(name_index)
        damage = wksht.value(damage_index)
        bonus = wksht.value(bonus_index)
        details = None

        if not name:
            return None
        if not damage:
            damage = None
        else:
            details = None
            if "|" in damage:
                damage, details = damage.split("|", 1)
            try:
                dice, comment = get_roll_comment(damage.strip())
            except RollSyntaxError as e:
                raise AttackSyntaxError(name, damage_index, wksht.worksheet.title, e)
            if details:
                details = details.strip()
            if any(d in comment.lower() for d in DAMAGE_TYPES):
                damage = "{}[{}]".format(dice, comment)
            else:
                damage = dice
                if comment.strip() and not details:
                    damage = comment.strip()
        if bonus:
            try:
                bonus = int(bonus)
            except (TypeError, ValueError):
                bonus = None
        else:
            bonus = None
        attack = Attack.new(name, bonus, damage, details)
        return attack

    def _get_potential_spells(self):
        """Return a list of tuples of (spell_name, prepared)"""
        if "noprep" in self.args:
            # spells C96:AH143
            potential_spells = [(sn, True) for sn in self.character_data.value_range("D96:AH143")]
            if self.additional:
                potential_spells.extend((sn, True) for sn in self.additional.value_range("D17:AH64"))
        else:
            potential_spells = []
            for spell_col, prep_col, rows in SPELL_RANGES:
                potential_spells.extend(self._process_spell_range(spell_col, prep_col, rows, self.character_data))
            if self.additional:
                for spell_col, prep_col, rows in SPELL_RANGES_ADDITIONAL:
                    potential_spells.extend(self._process_spell_range(spell_col, prep_col, rows, self.additional))
        return potential_spells

    def _process_spell_range(self, spell_col, prep_col, rows, worksheet):
        for row in rows:
            cell = f"{spell_col}{row}"
            spell_name = worksheet.value(cell)
            if not spell_name:
                continue
            if prep_col is None:
                prepared = True
            else:
                prepared_cell = f"{prep_col}{row}"
                val = worksheet.unformatted_value(prepared_cell)
                prepared = val and val != "0"
            yield spell_name, prepared
