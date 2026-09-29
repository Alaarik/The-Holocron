import disnake
from utils.argparser import argparse

class CombatView(disnake.ui.View):
    def __init__(self, inter, weapon, target, character):
        super().__init__(timeout=180)
        self.inter = inter
        self.weapon = weapon
        self.target = target
        self.character = character
        
        # Determine available modifiers
        self.valid_modifiers = []
        
        pools = []
        if hasattr(self.character, 'attacks') and self.character.attacks:
            pools.extend(self.character.attacks)
        if hasattr(self.character, 'actions') and self.character.actions:
            pools.extend(self.character.actions)
            
        for feature in pools:
            if feature.name in [
                "Sneak Attack", 
                "Force-Empowered Strikes", 
                "Ranger's Quarry", 
                "Kinetic Combat", 
                "Superiority Die",
                "The Way of the Krayt Dragon",
                "Sharp Instincts",
                "Critical Analysis"
            ]:
                if feature.name not in self.valid_modifiers:
                    self.valid_modifiers.append(feature.name)
                
            if feature.name in ["Makashi Form", "Makashi Technique"]:
                if "Makashi Technique" not in self.valid_modifiers: self.valid_modifiers.append("Makashi Technique")
            if feature.name in ["Juyo Form", "Juyo Technique"]:
                if "Juyo Technique" not in self.valid_modifiers: self.valid_modifiers.append("Juyo Technique")
            if feature.name in ["Niman Form", "Niman Technique"]:
                if "Niman Technique" not in self.valid_modifiers: self.valid_modifiers.append("Niman Technique")
            if feature.name in ["Shien Form", "Shien Technique"]:
                if "Shien Technique" not in self.valid_modifiers: self.valid_modifiers.append("Shien Technique")
            if feature.name in ["Vaapad Form", "Vaapad Technique"]:
                if "Vaapad Technique" not in self.valid_modifiers: self.valid_modifiers.append("Vaapad Technique")
                
        atk_obj = self.character.get_attack(self.weapon)
        is_attack = False
        if atk_obj and hasattr(atk_obj, "automation") and atk_obj.automation:
            for effect in atk_obj.automation:
                if effect.type == "target":
                    for sub_effect in effect.effects:
                        if sub_effect.type == "attack":
                            is_attack = True

        if self.valid_modifiers and is_attack:
            self.add_item(ModifierSelect(self.valid_modifiers))
        
        for child in self.children:
            if isinstance(child, disnake.ui.Button):
                child.label = f"Roll Attack" if is_attack else f"Use Action"


    @disnake.ui.button(label="Roll Attack", style=disnake.ButtonStyle.primary)
    async def confirm_roll(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if not interaction.response.is_done():
            await interaction.response.defer()
            
        args_str = ""
        if self.target:
            args_str += f"-t \"{self.target}\" "
            
        selected_mods = []
        for item in self.children:
            if isinstance(item, ModifierSelect):
                selected_mods = item.values
                break
                
        for mod_name in selected_mods:
            mod_atk = self.character.get_attack(mod_name)
            if mod_atk:
                if mod_name == "Sneak Attack":
                    import math
                    operative_levels = 0
                    for c in self.character.levels:
                        if c[0] == "Operative": operative_levels = c[1]
                    args_str += f"-d \"{math.ceil(operative_levels/2)}d6\" "
                elif mod_name == "Force-Empowered Strikes":
                    args_str += f"-d \"1d8\" " 
                    counter = self.character.get_consumable("Force Points")
                    if counter and counter.value > 0:
                        counter.set(counter.value - 1)
                        await self.character.commit(self.inter)
                elif mod_name == "Superiority Die":
                    f_lvl = 0
                    s_lvl = 0
                    for c in self.character.levels:
                        if c[0] == "Fighter": f_lvl = c[1]
                        if c[0] == "Scholar": s_lvl = c[1]
                    lvl = max(f_lvl, s_lvl)
                    die = 4 + 2 * ((lvl >= 5) + (lvl >= 9) + (lvl >= 13) + (lvl >= 17))
                    args_str += f"-d \"1d{die}\" "
                elif mod_name == "Critical Analysis":
                    int_mod = self.character.skills.intelligence.modifier
                    scholar_levels = sum(c[1] for c in self.character.levels if c[0] == "Scholar")
                    die = min(12, ((scholar_levels + 3) // 4) * 2 + 4)
                    args_str += f"-b \"{int_mod}\" -d \"1d{die}\" "
                elif mod_name == "Kinetic Combat":
                    lvl = 0
                    for c in self.character.levels:
                        if c[0] == "Sentinel": lvl = c[1]
                    die = 4 + 2 * ((lvl >= 5) + (lvl >= 9) + (lvl >= 13) + (lvl >= 17))
                    args_str += f"-d \"1d{die}\" "
                    counter = self.character.get_consumable("Force Points")
                    if counter and counter.value > 0:
                        counter.set(counter.value - 1)
                        await self.character.commit(self.inter)
                elif mod_name == "Sharp Instincts":
                    scholar_levels = 0
                    for c in self.character.levels:
                        if c[0] == "Scholar": scholar_levels = c[1]
                    die = 8 + 2 * ((scholar_levels >= 13) + (scholar_levels >= 17))
                    args_str += f"-d \"1d{die}\" "
                elif mod_name == "The Way of the Krayt Dragon":
                    # Krayt Dragon adds Strength Mod to damage
                    str_mod = self.character.skills.strength.modifier
                    args_str += f'-d "{str_mod}" '
                elif mod_name == "Ranger's Quarry":
                    scout_levels = 0
                    for c in self.character.levels:
                        if c[0] == "Scout": scout_levels = c[1]
                    die = 4 if scout_levels < 5 else 6 if scout_levels < 9 else 8 if scout_levels < 13 else 10 if scout_levels < 17 else 12
                    args_str += f"-d \"1d{die}\" "
                    
        from cogs5e.utils.actionutils import run_attack
        from cogs5e.utils.targetutils import maybe_combat
        
        args = argparse(args_str)
        atk = self.character.get_attack(self.weapon)
        embed = disnake.Embed()
        
        caster, targets, combat = await maybe_combat(self.inter, self.character, args)
            
        await run_attack(
            ctx=self.inter,
            embed=embed,
            args=args,
            caster=caster,
            attack=atk,
            targets=targets,
            combat=combat
        )
        
        await interaction.followup.send(embed=embed)


class ModifierSelect(disnake.ui.StringSelect):
    def __init__(self, valid_modifiers):
        options = [
            disnake.SelectOption(label=mod, description=f"Add {mod} to this attack") 
            for mod in valid_modifiers
        ]
        super().__init__(
            placeholder="Select Attack Modifiers...",
            min_values=0,
            max_values=len(valid_modifiers),
            options=options,
        )

    async def callback(self, interaction: disnake.MessageInteraction):
        await interaction.response.defer()
