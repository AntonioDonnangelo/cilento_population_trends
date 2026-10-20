# Cilento population trends (1982-2026)

12.08.2026

Population trends of 91 towns in the Cilento area (province of Salerno), using
ISTAT resident population data from 1982 to 2026. Linear and polynomial fits per
comune, a comparison between coastal and inland towns, maps of the population and
age change, and a 20-year projection.

![Cilento 1982-2026: change of the population and of the mean age by comune](results/png/infographic_map.png)

In 44 years the 91 towns lost 7.7% of their residents, from 247,872 to 228,858.
67 of them have fewer residents than in 1982, and the mean age went up by 11 years,
from 36.1 to 47.1. On the left of the infographic the population change of each
comune, on the right how many years its mean age went up.

The full report (in Italian) is in [`results/pdf/report_cilento.pdf`](results/pdf/report_cilento.pdf).
The main results are also shown in the readme.

## What the code does

### `analisi_comuni.py`

- Reads `popolazione_combinata_1982_2026.csv`, the yearly population by comune, age
  and sex. This file merges three ISTAT sources: the 1982-1991 population
  reconstruction, the 1992-2019 intercensal reconstruction and POSAS 2020-2026.
- For each town in `COMUNI` it computes:
  - absolute and % change between the first and the last year
  - a linear regression of population on year: slope (residents/year), its standard
    error, RMSE and R²
  - a degree-2 polynomial fit, used to project the population 20 years after the
    last year (2046). Projections are clipped at 0.
- Writes the summary table to `results/tabella_comuni.csv` and 7 plots to `results/png/`.

### `report.py`

- Reads `results/tabella_comuni.csv` and splits the towns into coastal (15) and
  inland (76).
- Computes the aggregate numbers and makes 7 more plots in `results/png/`.
- Writes `results/report.md` and converts it to PDF with pandoc
  (`results/pdf/report_cilento.pdf`).

### `maps.py`

- Downloads the municipal boundaries of the province of Salerno (ISTAT, via
  [geojson-italy](https://github.com/guglielmo/geojson-italy)) into `data/` the first
  time it runs.
- Joins them with `results/tabella_comuni.csv` and draws one map per variable:
  population in 1982 and 2026, inhabitants per km² in 2026, % change of the
  population and change of the mean age.
- The mean age comes from `popolazione_combinata_1982_2026.csv`. The 1982 source puts
  all ages from 85 up in one class, so in both years they are counted as 85.
- Puts the population change and the age change side by side in
  `results/png/infografica_mappe.png`.
- Run it after `analisi_comuni.py`. It needs `geopandas`.

### Output

```
results/
├── tabella_comuni.csv     summary table, one row per comune
├── report.md, report.css  report source
├── png/                   all plots, maps and the infographic
└── pdf/                   report_cilento.pdf
data/                      municipal boundaries, downloaded by maps.py
```

## Results

### Overall

Across the 91 towns the population went from **247,872 to 228,858** residents
(-19,014, **-7.7%**). Capaccio Paestum only has data from 2002, so its starting value
is from 2002. Without it the change is -9.3%.

67 towns out of 91 (74%) lost population. The median change is **-20.5%**,
33 towns lost more than 30% and 7 lost more than half:

| Largest losses | 1982 | 2026 | % |
| --- | ---: | ---: | ---: |
| Valle dell'Angelo | 553 | 217 | -60.8 |
| Sacco | 955 | 394 | -58.7 |
| Campora | 697 | 297 | -57.4 |
| Corleto Monforte | 1,063 | 462 | -56.5 |
| Piaggine | 2,239 | 1,056 | -52.8 |

| Largest gains | 1982 | 2026 | % |
| --- | ---: | ---: | ---: |
| Torchiara | 1,121 | 1,908 | +70.2 |
| Castelnuovo Cilento | 1,690 | 2,849 | +68.6 |
| Agropoli | 14,500 | 21,418 | +47.7 |
| Novi Velia | 1,648 | 2,328 | +41.3 |
| Prignano Cilento | 860 | 1,111 | +29.2 |

In absolute terms Agropoli is the outlier (+6,918 residents). The largest absolute
losses are in Castel San Lorenzo, Laurino, Piaggine, Castelcivita and Pisciotta,
between 1,135 and 1,258 residents each.

![Distribution of the % change](results/png/distribuzione_variazione.png)

![Top and bottom 10 comuni](results/png/classifica_estremi.png)

Normalized trajectories (first year = 100):

![Normalized trajectories](results/png/traiettorie_normalizzate.png)

### Coast vs inland

This is the main result. Coastal comuni have a median change of **+9.2%** (n=15),
inland comuni **-25.3%** (n=76), so the gap is about 35 percentage points. Taken as
groups, the coast went from 89,390 to 99,930 residents (+11.8%) and the inland from
158,482 to 128,928 (-18.6%). The coastal share of the population went from 36% to 44%.

13 inland comuni grew (Torchiara, Castelnuovo Cilento,
Novi Velia, Prignano Cilento, Giungano, ...), and 4 coastal ones shrank: Pisciotta
(-32.0%), Pollica (-31.8%), Sapri (-14.1%) and San Giovanni a Piro (-12.0%).

The size of the comune alone explains little: the correlation between the starting
population and the % change is r = 0.31.

![Coast vs inland](results/png/costa_vs_interno.png)

![% change vs size](results/png/dimensione_vs_variazione.png)

![Slope vs size](results/png/pendenza_vs_dimensione.png)

### Maps

The infographic at the top puts the change of the population next to the change of
the mean age. The mean age went up in every comune. The largest increases are in
Alfano (+20.3 years), Tortorella (+18.1) and Serramezzana (+17.7), the smallest in
Prignano Cilento (+3.9), Laureana Cilento (+4.0) and Sant'Arsenio (+5.4).

The single maps, including the population in 1982 and 2026 and the inhabitants per
km², are in `results/png/` (`mappa_*.png`).

### Age structure

Age pyramid of all the comuni together, 1982 vs 2026. The base is about half as
wide as in 1982, the largest cohorts are now around 50-65 years old, and there are
many more people over 80. In the 1982 source all ages from 85 up are in a single
class, which is why there's a spike at 85.

![Age pyramid](results/png/piramide_eta.png)

### Projections to 2046

The sum of the single linear fits gives -436 residents/year for the whole area,
about 220,000 residents in 2046.

![Aggregate trend](results/png/andamento_aggregato.png)

With the quadratic fit, 80 comuni out of 91 keep declining. Four of them go to zero
by 2046 (Campora, Rofrano, Sant'Angelo a Fasanella, Valle dell'Angelo), and
Roscigno is projected at 5 residents. The best prospects are Prignano Cilento
(+27.5%), Giungano (+23.0%) and Casal Velino (+21.6%).

![Projected change, top and bottom 10](results/png/proiezione_rischio_crescita.png)

![Trajectories and projections, top and bottom 10](results/png/traiettorie_rischio_crescita.png)

These numbers should be taken with care, because the parabola bends outside the
observed period. For comuni whose growth slowed down in recent years it bends
downwards: Agropoli is projected at -12.7%, and Capaccio Paestum drops from 22,463
to 13,839. For declining comuni it makes the decline steeper than the historical
trend: Rofrano goes to 0 with the quadratic fit, but the linear trend would give
about 640 residents in 2046. They show where the trend points, they aren't forecasts.

### Per-comune plots

![Yearly slope with standard error](results/png/pendenza.png)
