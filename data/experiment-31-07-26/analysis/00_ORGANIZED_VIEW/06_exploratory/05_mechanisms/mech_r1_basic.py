import json, statistics as st
D=[r for r in json.load(open('paired_clean.json')) if r['analysis_include']]
print("cells", len(D), "items", len({r['question_id'] for r in D}), "models", sorted({r['model'] for r in D}))
by={}
for r in D: by.setdefault(r['model'],[]).append(r)
print(f"{'model':40s} {'n':>5} {'medA':>7} {'medB':>7} {'medDiff':>8} {'meanA':>8} {'meanB':>8} {'meanDiff':>9} {'accA':>6} {'accB':>6}")
for m,rows in sorted(by.items()):
    dA=[r['A_tokens'] for r in rows]; dB=[r['B_tokens'] for r in rows]
    dd=[r['B_tokens']-r['A_tokens'] for r in rows]
    print(f"{m:40s} {len(rows):5d} {st.median(dA):7.1f} {st.median(dB):7.1f} {st.median(dd):8.1f} {st.mean(dA):8.1f} {st.mean(dB):8.1f} {st.mean(dd):9.1f} {sum(r['A_correct'] for r in rows)/len(rows):6.3f} {sum(r['B_correct'] for r in rows)/len(rows):6.3f}")
dd=[r['B_tokens']-r['A_tokens'] for r in D]
print("\nALL: medianDiff", st.median(dd), "meanDiff", round(st.mean(dd),1), "frac B>A", round(sum(1 for x in dd if x>0)/len(dd),4), "frac B<A", round(sum(1 for x in dd if x<0)/len(dd),4), "frac tie", round(sum(1 for x in dd if x==0)/len(dd),4))
