"""One-off inspection: rapidfuzz.fuzz.partial_ratio_alignment's return shape."""
from rapidfuzz import fuzz

aln = fuzz.partial_ratio_alignment("hello world", "xxx hello wrld yyy")
print(aln)
print(type(aln))
print("score", aln.score)
print("src_start/end", aln.src_start, aln.src_end)
print("dest_start/end", aln.dest_start, aln.dest_end)
