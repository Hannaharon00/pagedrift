"""
History/diff rendering for the restock_diff (price / stock availability) processor.

A text diff is meaningless for restock watches - each history snapshot is just a short
string like "In Stock: True - Price: 12.34". So instead of a diff, this renders the whole
timeline as a simple smoothed line graph of price over time, coloured green where the item
was in stock and red where it was out of stock.

