# Original vs generated pipeline (Chicago, 24 benchmark moments)

| | original | generated |
|---|---|---|
| panel mean (1-5) | 4.12 | 3.90 |
| style_match | 4.08 | 4.10 |
| composition_intact | 4.33 | 4.29 |
| realism | 3.96 | 3.90 |
| light_consistency | 3.62 | 3.33 |
| season_correct | 4.77 | 4.17 |
| edges_artifacts | 4.12 | 3.75 |
| would_set_as_wallpaper | 3.92 | 3.73 |
| structure kept (edge recall vs painting) | 0.990 | 0.950 |
| render time per frame (s) | 2.53 | 1.21 |

Blind pairwise votes (48 = 24 moments x 2 models): original 34, generated 14, tie 0

| moment | orig | gen | votes |
|---|---|---|---|
| 01_spring_clear | 4.00 | 3.43 | qwen3.5:original, inkling-2-mini:original |
| 02_spring_partly_cloudy | 4.57 | 3.43 | qwen3.5:original, inkling-2-mini:original |
| 03_spring_clear | 4.21 | 3.71 | qwen3.5:original, inkling-2-mini:original |
| 04_spring_clear | 4.50 | 3.50 | qwen3.5:original, inkling-2-mini:original |
| 05_spring_rain | 4.07 | 4.07 | qwen3.5:original, inkling-2-mini:original |
| 06_spring_storm | 4.57 | 3.71 | qwen3.5:original, inkling-2-mini:original |
| 07_spring_fog | 3.21 | 4.43 | qwen3.5:original, inkling-2-mini:original |
| 08_summer_clear | 4.64 | 4.36 | qwen3.5:generated, inkling-2-mini:original |
| 09_summer_partly_cloudy | 3.29 | 3.21 | qwen3.5:original, inkling-2-mini:original |
| 10_summer_clear | 4.00 | 3.79 | qwen3.5:generated, inkling-2-mini:original |
| 11_summer_storm | 4.00 | 3.86 | qwen3.5:original, inkling-2-mini:original |
| 12_summer_rain | 4.29 | 3.79 | qwen3.5:original, inkling-2-mini:generated |
| 13_autumn_clear | 4.57 | 4.36 | qwen3.5:generated, inkling-2-mini:generated |
| 14_autumn_partly_cloudy | 4.57 | 3.43 | qwen3.5:generated, inkling-2-mini:original |
| 15_autumn_clear | 4.29 | 4.00 | qwen3.5:generated, inkling-2-mini:original |
| 16_autumn_rain | 4.64 | 3.43 | qwen3.5:original, inkling-2-mini:original |
| 17_autumn_fog | 3.50 | 4.14 | qwen3.5:original, inkling-2-mini:generated |
| 18_autumnlate_snow | 3.14 | 4.21 | qwen3.5:generated, inkling-2-mini:generated |
| 19_winter_clear | 4.07 | 4.07 | qwen3.5:original, inkling-2-mini:original |
| 20_winter_clear | 4.21 | 4.64 | qwen3.5:generated, inkling-2-mini:original |
| 21_winter_clear | 4.57 | 4.57 | qwen3.5:generated, inkling-2-mini:original |
| 22_winter_snow | 4.57 | 4.07 | qwen3.5:original, inkling-2-mini:generated |
| 23_winterbare_overcast | 3.07 | 3.14 | qwen3.5:generated, inkling-2-mini:original |
| 24_winter_fog | 4.21 | 4.14 | qwen3.5:original, inkling-2-mini:original |
