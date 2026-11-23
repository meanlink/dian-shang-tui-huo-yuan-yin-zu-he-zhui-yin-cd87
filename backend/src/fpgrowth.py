"""FP-tree with weighted conditional prefix paths for bounded frequent itemsets."""
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from fractions import Fraction


@dataclass(eq=False)
class Node:
    item: str
    parent: 'Node | None' = None
    count: int = 0
    children: dict[str, 'Node'] = field(default_factory=dict)


def fp_growth(transactions, minimum, max_size=3):
    def mine(paths, suffix):
        counts = Counter()
        for items, weight in paths:
            for item in items:
                counts[item] += weight
        root = Node('')
        header = defaultdict(list)
        for items, weight in paths:
            node = root
            ordered = sorted((item for item in items if counts[item] >= minimum),
                             key=lambda item: (-counts[item], item))
            for item in ordered:
                if item not in node.children:
                    node.children[item] = Node(item, node)
                    header[item].append(node.children[item])
                node = node.children[item]
                node.count += weight
        for item, nodes in sorted(header.items(), key=lambda pair: (counts[pair[0]], pair[0])):
            pattern = suffix | {item}
            yield pattern, sum(node.count for node in nodes)
            if len(pattern) == max_size:
                continue
            conditional = []
            for node in nodes:
                prefix = []
                ancestor = node.parent
                while ancestor.parent is not None:
                    prefix.append(ancestor.item)
                    ancestor = ancestor.parent
                if prefix:
                    conditional.append((prefix, node.count))
            yield from mine(conditional, pattern)

    return dict(mine([(frozenset(transaction), 1) for transaction in transactions], frozenset()))


def rank_rules(samples, minimum=3):
    # Sample is one inspected return; warehouse finding is independent of service labels.
    transactions = [(row['ticket'], set(row['symptoms']) | {row['finding']}) for row in samples]
    findings = {row['finding'] for row in samples}
    supports = fp_growth([items for _, items in transactions], minimum)
    rules = []
    for pattern, count in supports.items():
        outcomes = pattern & findings
        symptoms = pattern - findings
        if len(outcomes) != 1 or not symptoms:
            continue
        finding = next(iter(outcomes))
        baseline = supports[outcomes]
        denominator = supports[symptoms]
        lift = Fraction(count * len(samples), denominator * baseline)
        rules.append((lift, count, sorted(symptoms), finding, denominator, baseline,
                      sorted(ticket for ticket, items in transactions if pattern <= items)))
    return sorted(rules, key=lambda rule: (-rule[0], -rule[1], rule[2], rule[3]))
