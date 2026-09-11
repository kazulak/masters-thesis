#!/usr/bin/env python3
"""Plot the original accepted P6 contrasts without recalculating statistics."""
import argparse
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['svg.hashsalt']='masters-thesis-final-evaluation-v1'
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--p6',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();folder=Path(a.output);folder.mkdir(parents=True,exist_ok=False)
    with (Path(a.p6)/'contrasts.csv').open() as fp:rows=list(csv.DictReader(fp))
    for contrast in ('R/U','G/U'):
        rs=[r for r in rows if r['metric']=='session_inclusive_s' and r['contrast']==contrast]
        rs.sort(key=lambda r:r['cell_id'])
        fig,ax=plt.subplots(figsize=(9,5))
        ratio=[float(r['ratio_of_medians']) for r in rs]
        lo=[float(r['paired_bootstrap_low']) for r in rs];hi=[float(r['paired_bootstrap_high']) for r in rs]
        # Draw stored CI endpoints directly; no assumption that every percentile interval encloses its estimate.
        for i,(point,left,right) in enumerate(zip(ratio,lo,hi)):
            ax.plot([left,right],[i,i],linewidth=1);ax.scatter(point,i,s=22)
        ax.axvline(1,linestyle='--');ax.set_yticks(range(len(rs)),[r['cell_id'] for r in rs],fontsize=7)
        ax.set_xlabel(f'{contrast} session-inclusive ratio; >1 favors U')
        ax.set_title('Original P6: stored descriptive paired-block intervals')
        fig.tight_layout();stem=contrast.replace('/','_over_')
        fig.savefig(folder/f'{stem}.svg',metadata={'Date':None,'Creator':'masters-thesis final evaluation v1'});fig.savefig(folder/f'{stem}.png',dpi=180);plt.close(fig)


if __name__=='__main__':main()
