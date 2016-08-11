import urllib2
from bs4 import BeautifulSoup as bs
import sys, os, hashlib, re
from urlparse import urljoin

results_url = sys.argv[1]

results = bs(urllib2.urlopen(results_url).read(), 'lxml')

round_links = []
for link in results.select('a[href]'):
    if '/RoundTeams.asp' in link['href']:
        round_links.append(link['href'])

class Round:
    tournament = ''
    name = ''
    content = ''

    def __repr__(self):
        return self.tournament + ': ' + self.name

    def __eq__(self, other):
        return self.tournament == other.tournament and self.name == other.name

round_regex = re.compile('^round ', flags=re.I)
rounds = []
for r in set(round_links):
    round_hash = hashlib.sha224(results_url + r).hexdigest()
    cache_path = os.path.join('cache', round_hash)
    if not os.path.exists(cache_path):
        r_content = urllib2.urlopen(urljoin(results_url, r)).read()
        file(cache_path, 'w').write(r_content)
    else:
        r_content = file(cache_path).read()
    content = bs(r_content, 'lxml')
    first_row = content.select('table tr')[0]
    cells = [cell.text.strip() for cell in first_row.select('td')]
    round_cells = [cell for cell in cells if round_regex.match(cell)]
    other_cells = [cell for cell in cells if not round_regex.match(cell)]
    new_round = Round()
    new_round.name = ' '.join(round_cells)
    new_round.tournament = ' - '.join(other_cells)
    new_round.content = content
    if new_round not in rounds:
        rounds.append(new_round)

for r in rounds:
    print r
