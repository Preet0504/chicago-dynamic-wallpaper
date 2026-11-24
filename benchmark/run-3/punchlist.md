# Run 3 punchlist (grouped by owner, most impactful first)

Run 3 avg 3.84 (run 2: 3.79, run 1: 3.16). New autumnlate (18) and winterbare (23) scenes fixed the two RULES.md failures: both now score 4s.

## season-modifier (winter snowy template, summer, autumn)
1. Winter snowy walkway (items 19, 20, 21, 22, 24): still a flat, blown-out white sheet with a hard cut top edge that buries the railing (a rejected pattern from SKILL.md). It needs a contoured blanket that follows the stone rows, with drifts at the rail and lantern bases and soft footprints. Keep the railing and lantern bases visible.
2. Bottom-left foreground: the roof turned into a giant white slab that dominates the corner and drifts from the layout. Restore roof tile structure under thin snow caps.
3. Pavilion base turned into a stone wall (layout drift) and snow-covered shrubs sit in front of the railing. Restore the original pavilion base.
4. Snow walkway at night (item 22): the sheet is now flat dark grey with a hard curved white lip, which is worse than run 2. Make it a smooth blanket that picks up lantern warmth (a weather-modifier snow task too).
5. No lake ice or shore snow anywhere in winter. Add a broken ice/snow edge along the near shore.
6. Summer (8, 9, 10, 11, 12): leaf cluster is lime ivy-like shapes with hard black outlines, off-style. Redo as painted foliage clumps with soft shading and darker interior. The path is over-saturated pink-red in item 8.
7. Autumn (13, 15, 17): white halo outlines around leaf clusters and a blue-teal fringe around the pagoda roofs, leaves and mountain ridge at night. Pixel-block artifacts in the top-left leaf cluster in the fog frame (17).
8. Autumnlate (18): a dark green blob left of the pagoda at ~(285,720), floating twig fragments under the branch at ~(1050,370), and slightly pixelated bare twigs.
9. Winterbare (23): faint blotches in the top-left sky; twig fragments at the branch tip (~1000-1080, 340-370). Shrubs are a flat sepia tone.

## time-modifier
1. Sun in autumn (13): the disc and halo sit directly behind the pagoda spire. Move it or reduce the halo.
2. Daytime clouds (2, 9, 14): blurry soft blobs, not painted. Rectangular cloud blocks remain at the mountain base (9 at x~950-1030, y~600; 14 at right horizon x~1200). Repaint with hard-edged anime cloud shapes.
3. Winter day sun (19): a flat cartoon disc with halo. Give it a softer, smaller sun and a lighter sky near it.
4. Hard-edged dark band along the right hill and horizon strip (4, 6, 10), partly improved. Feather it fully.
5. Lake in the day (2, 8, 13): blown-out pale water, golden smudge patch at the right shore, brown smoky smudges on the far shore. Clean these up.
6. Fireflies on summer nights are still missing (10, 12). RULES.md requires them (realism capped at 3 for 10).
7. Winter clear night (21): no moon, though the rules say the moon should be visible on a clear night.

## weather-modifier
1. Storm (6, 11): lightning ends on a flat dark band above the mountain base. Fade the bolt into cloud or the horizon.
2. Rain (5, 12, 16): lake is speckle noise. Use ripple rings plus a soft sheen. Mist smudges at the pagoda base (5).
3. Snow (22): flakes tiny and sparse, with no large blurry near layer. The sky is a flat dark fill; add cloud texture.
4. Autumnlate snow (18): good. Keep the dusting light and avoid uniform frost over the whole town.
5. Fog (7, 17, 24): flat beige/grey sky. Add subtle vertical gradient or cloud mottling. The unlit hanging lantern still looks ghostly in autumn fog (17).

## detail-orienter
1. Hanging lantern: unlit-day grey ghost look in rain/fog (5, 11, 17); in winter, the snow cap reads as a mushroom with a stray white arc (19, 20, 21).
2. Pagoda windows glow yellow-green in the spring day (2); white window glints at pagoda base in some frames. Check that lanterns and windows are fully off in the day.
3. Autumn pagoda spire shows a glow smear at night (15) and a ghost double at fog (17).
4. Left lake edge / far shore smudges and the dark rectangular patch beside the pagoda base (several frames).

## template-creator
1. Winter template geometry: re-derive from the spring layout so the walkway, railing, pavilion base and bottom-left roofs match the original composition.
2. Autumn template offset from the shared composition (pagoda and horizon sit slightly differently); align or note it for downstream modifiers.
3. Summer template: replace the lime leaf cluster and brown shore smudges at the source.
4. Autumnlate and winterbare templates work; use them as the model (bare branch, dormant shrubs, no lying snow) for March bare-with-buds spring if needed.
