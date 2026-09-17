from gamedata.compendium import compendium

for c in compendium.classes:
    if c.name == "Guardian":
        print(c.name, c.subclass_title)
