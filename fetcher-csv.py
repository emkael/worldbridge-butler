import urllib2
from bs4 import BeautifulSoup as bs
import sys, os, hashlib, re
from urlparse import urljoin
from math import floor

results_url = sys.argv[1]

def fetch_url(url):
    round_hash = hashlib.sha224(url).hexdigest()
    cache_path = os.path.join('cache', round_hash)
    if not os.path.exists(cache_path):
        r_content = urllib2.urlopen(url).read()
        file(cache_path, 'w').write(r_content)
    else:
        r_content = file(cache_path).read()
    return r_content

results = bs(fetch_url(results_url), 'lxml')

round_links = []
for link in results.select('a[href]'):
    if '/RoundTeams.asp' in link['href']:
        round_links.append(link['href'])

class Round:
    tournament = None
    url = ''
    name = ''
    content = ''
    tables = None
    boards = None

    def __init__(self):
        self.tables = []
        self.boards = {}

    def number(self):
        return int(re.sub('\b*round\b*', '', self.name, flags=re.I))

    def __repr__(self):
        return self.tournament.name + ': ' + self.name

    def __eq__(self, other):
        return self.tournament == other.tournament and self.name == other.name

    def __gt__(self, other):
        return self.number() > other.number()

round_regex = re.compile('^round ', flags=re.I)
rounds = []
for r in set(round_links):
    url = urljoin(results_url, r)
    content = bs(fetch_url(url), 'lxml')
    first_row = content.select('table tr')[0]
    cells = [cell.text.strip() for cell in first_row.select('td')]
    round_cells = [cell for cell in cells if round_regex.match(cell)]
    other_cells = [cell for cell in cells if not round_regex.match(cell)]
    new_round = Round()
    new_round.name = ' '.join(round_cells)
    new_round.tournament = ' - '.join(other_cells)
    new_round.content = content
    new_round.url = url
    if new_round not in rounds:
        rounds.append(new_round)

tournament_data = {}
for r in rounds:
    if r.tournament not in tournament_data:
        tournament_data[r.tournament] = []
    tournament_data[r.tournament].append(r)

class Tournament:
    name = ''
    rounds = None
    lineup = None

    def __init__(self, name, rounds):
        self.lineup = []
        self.name = name
        self.rounds = rounds
        for round in rounds:
            round.tournament = self

    def __repr__(self):
        return '%s (%d rounds)' % (self.name, len(self.rounds))

tournaments = []
for tour in tournament_data:
    tournaments.append(Tournament(tour, tournament_data[tour]))

class Table:
    results = None
    content = ''

    def __init__(self):
        self.results = []

class Pair:
    first_name = ''
    second_name = ''
    nation = ''
    results = None

    def __init__(self, name1, name2, nation):
        self.results = []
        self.first_name = name1
        self.second_name = name2
        self.nation = nation

    def __eq__(self, other):
        return ' - '.join(sorted([self.first_name, self.second_name])) == \
            ' - '.join(sorted([other.first_name, other.second_name]))

    def __repr__(self):
        return '%s - %s (%s)' % (self.first_name, self.second_name, self.nation)

    def __hash__(self):
        return int(hashlib.sha224(self.__repr__()).hexdigest(), 16)

class Result:
    ns_pair = None
    ew_pair = None
    tour_round = None
    board_no = 0
    score = 0
    butler = 0
    cutoff_butler = 0
    cavendish = 0

    def __init__(self, ns, ew, score, rnd, board):
        self.ns_pair = ns
        self.ew_pair = ew
        self.score = score
        self.tour_round = rnd
        self.board_no = board
        self.ns_pair.results.append(self)
        self.ew_pair.results.append(self)

    def __gt__(self, other):
        return self.score > other.score

    def __repr__(self):
        return '%d-%d\t%d\t%d\t%d\t%f' % (self.tour_round.number(), self.board_no,
                                          self.score,
                                          self.butler, self.cutoff_butler,
                                          self.cavendish)

for tour in tournaments:
    for r in tour.rounds:
        table_urls = [urljoin(r.url, link['href']) for link in r.content.select('a[href]') if 'BoardDetails.asp' in link['href']]
        for url in table_urls:
            table = Table()
            table.content = bs(fetch_url(url), 'lxml')
            team_links = [link for link in table.content.select('div[align] a[href]') if 'TeamDetails.asp' in link['href']]
            if len(team_links) == 2:
                home_team = team_links[0].text
                away_team = team_links[1].text
                players = [link.text.strip() for link in table.content.select('a[href]') if 'people/person.asp' in link['href']]
                if len(players) == 8:
                    pairs = [
                        Pair(players[0], players[6], home_team), # open
                        Pair(players[4], players[5], home_team), # closed
                        Pair(players[2], players[3], away_team), # open
                        Pair(players[1], players[7], away_team)  # closed
                    ]
                    for i, pair in enumerate(pairs):
                        try:
                            pairs[i] = tour.lineup[tour.lineup.index(pair)]
                        except ValueError:
                            tour.lineup.append(pair)
                    result_cells = [int(cell.text.strip()) if len(cell.text.strip()) > 0 else 0 for cell in table.content.select('tr[nowrap] b')]
                    open_scores = []
                    closed_scores = []
                    for i in range(0, len(result_cells) / 6):
                        open_scores.append(result_cells[6*i] - result_cells[6*i + 1])
                        closed_scores.append(result_cells[6*i + 2] - result_cells[6*i + 3])
                    for board, score in enumerate(open_scores):
                        new_score = Result(pairs[0], pairs[2], score, r, board+1)
                        table.results.append(new_score)
                    for board, score in enumerate(closed_scores):
                        new_score = Result(pairs[3], pairs[1], score, r, board+1)
                        table.results.append(new_score)
            r.tables.append(table)
    for r in tour.rounds:
        for table in r.tables:
            for result in table.results:
                if result.board_no not in r.boards:
                    r.boards[result.board_no] = []
                r.boards[result.board_no].append(result)

def imp(res1, res2):
    diff = res1 - res2
    ew = False
    if diff < 0:
        ew = True
        diff = -diff
    thresholds = [20, 50, 90, 130, 170, 220, 270, 320, 370, 430,
                  500, 600, 750, 900, 1100, 1300, 1500, 1750,
                  2000, 2250, 2500, 3000, 3500, 4000]
    imps = len([t for t in thresholds if diff >= t])
    return -imps if ew else imps

def get_datum(board):
    average = float(sum([r.score for r in board])) / len(board)
    return int(round(average / 10)) * 10

for tour in tournaments:

    if len(tour.lineup) == 0:
        continue

    for rnd in tour.rounds:
        for i, board in rnd.boards.iteritems():
            datum = get_datum(board)
            cutoff = int(floor(len(board) / 4))
            cutoff_results = sorted(board)
            cutoff_datum = get_datum(cutoff_results[cutoff:-cutoff])
            for r in board:
                r.butler = imp(r.score, datum)
                r.cutoff_butler = imp(r.score, cutoff_datum)
                r.cavendish = float(sum([imp(r.score, other.score) for other in board if r <> other])) / float((len(board) - 1))

    print tour.name

    for pair in tour.lineup:
        #print pair
        result_table = []
        for res in pair.results:
            ew = -1 if res.ew_pair == pair else 1
            result_table.append([
                res.tour_round.number(),
                res.board_no,
                res.score,
                ew * res.butler,
                ew * res.cutoff_butler,
                ew * res.cavendish
            ])
        for r in sorted(result_table, cmp=lambda x,y: cmp(x[0], y[0]) or cmp(x[1], y[1])):
            print '\t'.join([str(pair)] + [str(s) for s in r[:3]] + [str(round(s, 2)) for s in r[3:]])
        #print '\t'.join([
        #    str(len(result_table)),
        #    '',
        #    '',
        #    str(round(float(sum([r[3] for r in result_table])) / float(len(result_table)), 2)),
        #    str(round(float(sum([r[4] for r in result_table])) / float(len(result_table)), 2)),
        #    str(round(float(sum([r[5] for r in result_table])) / float(len(result_table)), 2))
        #])
        #print
    print

    head_to_head = {}
    for r in tour.rounds:
        for table in r.tables:
            for result in table.results:
                if result.ns_pair not in head_to_head:
                    head_to_head[result.ns_pair] = {}
                if result.ew_pair not in head_to_head[result.ns_pair]:
                    head_to_head[result.ns_pair][result.ew_pair] = []
                if result.ew_pair not in head_to_head:
                    head_to_head[result.ew_pair] = {}
                if result.ns_pair not in head_to_head[result.ew_pair]:
                    head_to_head[result.ew_pair][result.ns_pair] = []
                head_to_head[result.ns_pair][result.ew_pair].append([
                    result.butler,
                    result.cutoff_butler,
                    result.cavendish
                ])
                head_to_head[result.ew_pair][result.ns_pair].append([
                    -result.butler,
                    -result.cutoff_butler,
                    -result.cavendish
                ])
    for ns in head_to_head:
        for ew in head_to_head[ns]:
            count = float(len(head_to_head[ns][ew]))
            head_to_head[ns][ew] = {
                'butler': float(sum([r[0] for r in head_to_head[ns][ew]])) / count,
                'cutoff_butler': float(sum([r[1] for r in head_to_head[ns][ew]])) / count,
                'cavendish': float(sum([r[2] for r in head_to_head[ns][ew]])) / count,
                'count': count
            }
    normalized = {}
    for ns in head_to_head:
        if ns not in normalized:
            normalized[ns] = {
                'butler': 0,
                'cutoff_butler': 0,
                'cavendish': 0,
                'count': 0
            }
        for ew in head_to_head[ns]:
            head_to_head[ns][ew]['opposition'] = {
                'butler': 0,
                'cutoff_butler': 0,
                'cavendish': 0,
                'count': 0
            }
            for opposition in head_to_head[ew]:
                if opposition != ns:
                    head_to_head[ns][ew]['opposition']['butler'] += head_to_head[ew][opposition]['butler'] * head_to_head[ew][opposition]['count']
                    head_to_head[ns][ew]['opposition']['cutoff_butler'] += head_to_head[ew][opposition]['cutoff_butler'] * head_to_head[ew][opposition]['count']
                    head_to_head[ns][ew]['opposition']['cavendish'] += head_to_head[ew][opposition]['cavendish'] * head_to_head[ew][opposition]['count']
                    head_to_head[ns][ew]['opposition']['count'] += head_to_head[ew][opposition]['count']
            if head_to_head[ns][ew]['opposition']['count'] > 0:
                head_to_head[ns][ew]['opposition']['butler'] /= head_to_head[ns][ew]['opposition']['count']
                head_to_head[ns][ew]['opposition']['cutoff_butler'] /= head_to_head[ns][ew]['opposition']['count']
                head_to_head[ns][ew]['opposition']['cavendish'] /= head_to_head[ns][ew]['opposition']['count']
            normalized_butler = head_to_head[ns][ew]['butler'] + head_to_head[ns][ew]['opposition']['butler']
            normalized_cutoff = head_to_head[ns][ew]['cutoff_butler'] + head_to_head[ns][ew]['opposition']['cutoff_butler']
            normalized_cavendish = head_to_head[ns][ew]['cavendish'] + head_to_head[ns][ew]['opposition']['cavendish']
            normalized[ns]['butler'] += normalized_butler * head_to_head[ns][ew]['count']
            normalized[ns]['cutoff_butler'] += normalized_cutoff * head_to_head[ns][ew]['count']
            normalized[ns]['cavendish'] += normalized_cavendish * head_to_head[ns][ew]['count']
            normalized[ns]['count'] += head_to_head[ns][ew]['count']
            print '%s\t%s\t%.2f\t%.2f\t%.2f\t%.2f\t%.2f\t%.2f\t%.2f\t%.2f\t%.2f' % (
                str(ns),
                str(ew),
                head_to_head[ns][ew]['butler'],
                head_to_head[ns][ew]['cutoff_butler'],
                head_to_head[ns][ew]['cavendish'],
                head_to_head[ns][ew]['opposition']['butler'],
                head_to_head[ns][ew]['opposition']['cutoff_butler'],
                head_to_head[ns][ew]['opposition']['cavendish'],
                normalized_butler,
                normalized_cutoff,
                normalized_cavendish
            )
    print
    for pair in normalized:
        print '%s\t%.2f\t%.2f\t%.2f\t%d' % (
            str(pair),
            normalized[pair]['butler'] / normalized[pair]['count'],
            normalized[pair]['cutoff_butler'] / normalized[pair]['count'],
            normalized[pair]['cavendish'] / normalized[pair]['count'],
            normalized[pair]['count']
        )
    print
