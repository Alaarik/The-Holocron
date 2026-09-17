import re
SW5E_URL_RE = re.compile(r"https?://(?:www\.)?sw5e\.com/characters?/([a-zA-Z0-9\-]+)")
print(SW5E_URL_RE.match("https://sw5e.com/characters/12345-abcde"))
