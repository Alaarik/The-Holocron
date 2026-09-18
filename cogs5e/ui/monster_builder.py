import re
import disnake
from cogs5e.models.homebrew import Bestiary
from gamedata.monster import Monster

def parse_stats(stat_str):
    nums = re.findall(r'-?\d+', stat_str)
    if len(nums) < 6:
        nums += ['10'] * (6 - len(nums))
    return {
        "strength": int(nums[0]),
        "dexterity": int(nums[1]),
        "constitution": int(nums[2]),
        "intelligence": int(nums[3]),
        "wisdom": int(nums[4]),
        "charisma": int(nums[5])
    }

def build_monster_dict(state):
    try:
        cr_val = float(state.cr) if '/' not in state.cr else eval(state.cr)
    except:
        cr_val = 1.0
    prof = max(2, (int(cr_val) - 1) // 4 + 2) if cr_val >= 1 else 2
    
    ac_match = re.search(r'\d+', state.ac)
    ac_val = int(ac_match.group(0)) if ac_match else 10
    
    hp_match = re.search(r'(\d+)', state.hp)
    hp_val = int(hp_match.group(1)) if hp_match else 10
    
    attacks = []
    traits = []
    
    for line in state.traits_actions.split('\n'):
        if not line.strip(): continue
        if ':' in line:
            title, desc = line.split(':', 1)
            title = title.strip()
            desc = desc.strip()
            atk_match = re.search(r'([+-]\d+)\s+to hit', desc)
            dmg_match = re.search(r'(\d+d\d+(?:\s*[+-]\s*\d+)?)', desc)
            
            if atk_match and dmg_match:
                attacks.append({
                    "name": title,
                    "attackBonus": atk_match.group(1).replace('+', ''),
                    "damage": dmg_match.group(1).replace(' ', '') + " [kinetic]",
                    "details": desc
                })
            else:
                traits.append({"name": title, "desc": desc})
        else:
            traits.append({"name": "Trait", "desc": line.strip()})
            
    stats = parse_stats(state.stats)
    
    # Apply proficiency to saves/skills based on string matches in state.saves_skills
    # Map skills to stats
    skill_to_stat = {
        "acrobatics": "dexterity", "animalHandling": "wisdom", "athletics": "strength", "deception": "charisma",
        "initiative": "dexterity", "insight": "wisdom", "intimidation": "charisma", "investigation": "intelligence",
        "lore": "intelligence", "medicine": "wisdom", "nature": "intelligence", "perception": "wisdom",
        "performance": "charisma", "persuasion": "charisma", "piloting": "intelligence", "sleightOfHand": "dexterity",
        "stealth": "dexterity", "survival": "wisdom", "technology": "intelligence", "strength": "strength",
        "dexterity": "dexterity", "constitution": "constitution", "intelligence": "intelligence", "wisdom": "wisdom",
        "charisma": "charisma"
    }

    # Initialize all skills/saves with base stat mod and prof=0
    saves = {k: {"value": (stats[k.replace('Save', '')] - 10) // 2, "prof": 0} for k in ["strengthSave", "dexteritySave", "constitutionSave", "intelligenceSave", "wisdomSave", "charismaSave"]}
    skills = {k: {"value": (stats[skill_to_stat[k]] - 10) // 2, "prof": 0} for k in skill_to_stat.keys()}
    
    # Apply proficiencies
    for word in state.saves_skills.lower().replace(',', ' ').split():
        if not word: continue
        for s in saves.keys():
            if s.lower().startswith(word):
                saves[s]["prof"] = 1
                saves[s]["value"] += prof
        for s in skills.keys():
            if s.lower().startswith(word):
                skills[s]["prof"] = 1
                skills[s]["value"] += prof
    
    data = {
        "name": state.name or "Unnamed Monster",
        "size": state.size_type_align.split(' ')[0] if ' ' in state.size_type_align else "Medium",
        "type": state.size_type_align,
        "alignment": "unaligned",
        "ac": str(ac_val),
        "hp": hp_val,
        "speed": state.speed,
        "ability_scores": stats,
        "skills": skills,
        "saves": saves,
        "cr": str(state.cr),
        "spellbook": {"slots": {"1":0,"2":0,"3":0,"4":0,"5":0,"6":0,"7":0,"8":0,"9":0}, "spells": [], "dc": 0, "sab": 0, "caster_level": 0, "spell_mod": 0, "at_will": [], "daily": {}},
        "traits": traits,
        "actions": [{"name": "Attacks", "desc": "See attacks list"}] if attacks else [],
        "reactions": [],
        "legactions": [],
        "attacks": attacks,
        "resistances": {"resist": [], "immune": [], "vuln": []},
        "display_resists": {"resist": "", "immune": "", "vuln": "", "condition": ""}
    }
    return data


class MonsterBuilderState:
    def __init__(self):
        self.name = ""
        self.ac = "10"
        self.hp = "10"
        self.speed = "30 ft."
        self.cr = "1"
        self.size_type_align = "Medium humanoid"
        self.stats = "10, 10, 10, 10, 10, 10"
        self.saves_skills = ""
        self.traits_actions = ""

class MonsterBasicsModal(disnake.ui.Modal):
    def __init__(self, view):
        self.builder_view = view
        components = [
            disnake.ui.TextInput(label="Name", custom_id="name", value=view.state.name, max_length=100),
            disnake.ui.TextInput(label="AC", custom_id="ac", value=view.state.ac, max_length=20),
            disnake.ui.TextInput(label="HP", custom_id="hp", value=view.state.hp, max_length=20),
            disnake.ui.TextInput(label="Speed", custom_id="speed", value=view.state.speed, max_length=50),
            disnake.ui.TextInput(label="Challenge Rating (CR)", custom_id="cr", value=view.state.cr, max_length=10),
        ]
        super().__init__(title="Monster Basics", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        self.builder_view.state.name = inter.text_values["name"]
        self.builder_view.state.ac = inter.text_values["ac"]
        self.builder_view.state.hp = inter.text_values["hp"]
        self.builder_view.state.speed = inter.text_values["speed"]
        self.builder_view.state.cr = inter.text_values["cr"]
        await self.builder_view.update_message(inter)

class MonsterStatsModal(disnake.ui.Modal):
    def __init__(self, view):
        self.builder_view = view
        components = [
            disnake.ui.TextInput(label="Size, Type, Alignment", custom_id="size", value=view.state.size_type_align, max_length=100),
            disnake.ui.TextInput(label="Ability Scores (STR DEX CON INT WIS CHA)", custom_id="stats", value=view.state.stats, max_length=50),
            disnake.ui.TextInput(label="Proficient Saves/Skills", custom_id="saves_skills", value=view.state.saves_skills, required=False, max_length=100),
        ]
        super().__init__(title="Monster Stats", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        self.builder_view.state.size_type_align = inter.text_values["size"]
        self.builder_view.state.stats = inter.text_values["stats"]
        self.builder_view.state.saves_skills = inter.text_values["saves_skills"]
        await self.builder_view.update_message(inter)

class MonsterActionsModal(disnake.ui.Modal):
    def __init__(self, view):
        self.builder_view = view
        components = [
            disnake.ui.TextInput(label="Traits and Actions", custom_id="traits_actions", value=view.state.traits_actions, style=disnake.TextInputStyle.paragraph, required=False, max_length=1000, placeholder="Blaster: +5 to hit, 1d8+3 energy\nKeen Sight: Advantage on perception..."),
        ]
        super().__init__(title="Monster Traits & Actions", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        self.builder_view.state.traits_actions = inter.text_values["traits_actions"]
        await self.builder_view.update_message(inter)

class BestiarySelectDropdown(disnake.ui.Select):
    def __init__(self, bestiaries):
        options = [disnake.SelectOption(label=b.name, value=str(b.id), description=f"{len(b.monsters)} monsters") for b in bestiaries]
        super().__init__(placeholder="Select a bestiary to save to...", min_values=1, max_values=1, options=options)

    async def callback(self, inter: disnake.MessageInteraction):
        await inter.response.defer()
        self.view.selected_bestiary_id = self.values[0]
        await self.view.do_save(inter)

class BestiarySelectView(disnake.ui.View):
    def __init__(self, bestiaries, state, bot):
        super().__init__()
        self.bestiaries = bestiaries
        self.state = state
        self.bot = bot
        self.selected_bestiary_id = None
        self.add_item(BestiarySelectDropdown(bestiaries))
        
    async def do_save(self, inter):
        bestiary_id = self.selected_bestiary_id
        selected_b = next(b for b in self.bestiaries if str(b.id) == bestiary_id)
        
        data = build_monster_dict(self.state)
        # Push to DB
        await self.bot.mdb.bestiaries.update_one(
            {"_id": selected_b.id},
            {"$push": {"monsters": data}}
        )
        
        await inter.edit_original_message(content=f"Successfully saved **{data['name']}** to bestiary **{selected_b.name}**!", view=None, embed=None)

class MonsterBuilderView(disnake.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=900)
        self.bot = bot
        self.state = MonsterBuilderState()

    def get_embed(self):
        embed = disnake.Embed(title=self.state.name or "Unnamed Monster", color=0x2ecc71)
        embed.description = f"*{self.state.size_type_align}*\n**AC** {self.state.ac} | **HP** {self.state.hp} | **Speed** {self.state.speed} | **CR** {self.state.cr}"
        embed.add_field(name="Stats", value=self.state.stats, inline=False)
        if self.state.saves_skills:
            embed.add_field(name="Proficiencies", value=self.state.saves_skills, inline=False)
        if self.state.traits_actions:
            embed.add_field(name="Traits & Actions", value=self.state.traits_actions[:1000], inline=False)
        return embed

    async def update_message(self, inter: disnake.ModalInteraction):
        await inter.response.edit_message(embed=self.get_embed(), view=self)

    @disnake.ui.button(label="Edit Basics", style=disnake.ButtonStyle.primary)
    async def edit_basics(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.send_modal(MonsterBasicsModal(self))

    @disnake.ui.button(label="Edit Stats", style=disnake.ButtonStyle.primary)
    async def edit_stats(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.send_modal(MonsterStatsModal(self))

    @disnake.ui.button(label="Edit Actions", style=disnake.ButtonStyle.primary)
    async def edit_actions(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.send_modal(MonsterActionsModal(self))

    @disnake.ui.button(label="Save Monster", style=disnake.ButtonStyle.success)
    async def save_monster(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        bestiaries = [b async for b in Bestiary.user_bestiaries(inter)]
        if not bestiaries:
            return await inter.response.send_message("You don't have any personal bestiaries to save to! Create one using `!bestiary create <name>`.", ephemeral=True)
            
        # load monsters length for display
        for b in bestiaries:
            await b.load_monsters(inter)
            
        if len(bestiaries) == 1:
            # just save it
            data = build_monster_dict(self.state)
            await self.bot.mdb.bestiaries.update_one(
                {"_id": bestiaries[0].id},
                {"$push": {"monsters": data}}
            )
            return await inter.response.edit_message(content=f"Successfully saved **{data['name']}** to bestiary **{bestiaries[0].name}**!", view=None, embed=None)
            
        # prompt selection
        view = BestiarySelectView(bestiaries, self.state, self.bot)
        await inter.response.edit_message(content="Multiple bestiaries found! Please select one:", view=view, embed=None)

