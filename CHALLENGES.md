# Challenges: why this is hard to sell (and what could help)

A frank list of what stands between wallgen and people paying for it, roughly from the biggest blocker down. Each
one has a possible way around it. Treat the licence notes as things to check, not legal advice.

## 1. The hardware almost nobody has

| What it needs today | What a typical buyer has |
|---|---|
| Apple-silicon Mac with **128 GB** of memory (the two review models alone are 81 GB + 20 GB) | 8–24 GB |
| **About 210 GB** of model downloads | 256–512 GB disk, already mostly full |
| A GPU busy for **~25 min** per picture, hot enough that macOS once forced a thermal sleep during a test | a laptop on battery |

Only a small fraction of Mac owners can run it as-is, and they're the people least likely to need a wallpaper app.

**Possible ways around it:**
- Run the heavy step for people (a hosted build) and ship only the scene package. The package is small, and the live
  wallpaper needs no AI. But that breaks "fully local", which is part of the pitch.
- Make a small-model tier: an 8–12B vision model as the screen and reviewer, and skip 4K upscaling. Then measure
  how much quality drops.
- Sell finished scene packages (curated pictures, already built) instead of the builder.

## 2. Setup is a developer project

Ollama, four model pulls, uv, mflux, two Python environments, a LaunchAgent. Every step can fail on a normal person's
machine, and the failures are cryptic (out-of-memory errors, Metal errors, a model tag that no longer exists).

**Possible ways around it:** a single signed app that bundles the runtime and downloads models with a progress bar;
a hardware check before anything downloads; one-click install of the wallpaper agent.

## 3. Quality is not yet better than free

Against a hand-built version of the same scene, the reviewers preferred the hand-built one: 4.12 vs 3.90, and 34 of
48 blind votes. The generated templates are greyer, the autumn colour is weaker, and snow doesn't settle on roofs.
People compare against Apple's built-in dynamic wallpapers, which are free and polished. "Close to hand-made" isn't
a reason to pay. The product has to be *obviously* better on *their own* picture.

**Possible ways around it:** close the quality gap first (see "Good first things to work on" in
[CONTRIBUTING.md](CONTRIBUTING.md)); let users reject a template and regenerate it with one click; show the 24-hour
strip before anything is installed, so the first impression is the best frames.

## 4. Waiting, and results that vary

About 4 minutes to the first wallpaper and about 25 for the full year is acceptable for a "make" button. It isn't
acceptable when the result disappoints and the only fix is to run it again. Image models vary between runs, and the
reviewers are noisy: the same image scored 3.8 one run and 5.0 the next. Some pictures will come out wrong, and the
user can't tell why.

**Possible ways around it:** show progress honestly (the web app already does); let people fix one season instead
of rerunning everything; calibrate the reviewers against real users' ratings, not model opinions.

## 5. Licences of the parts

Selling something built on models and data means every part must allow commercial use. Things to check before
charging anyone:

| Part | Concern (my understanding, verify against the current licence) |
|---|---|
| Depth Anything V2 **Base** | Published under a non-commercial licence (the Small variant is more permissive). Could swap it for a permissively licensed depth model. |
| Open-Meteo API | The free tier is for non-commercial use; commercial use needs a paid plan. |
| FLUX.2-klein, SeedVR2, Mask2Former, Grounding DINO, SAM | Check the model card and weights licence of each. Some image models ship non-commercial weights. |
| qwen3.5, qwen3, gpt-oss | Generally permissive, but confirm for the exact versions used. |
| inkling-2-mini | Licence unknown. Check it before shipping. |
| Users' uploaded pictures | Many people will upload art they don't own. Changing someone else's painting into a product feature is a copyright question, especially if packages can be shared or sold. |

## 6. Mac only, and hard to distribute

The wallpaper setter, the LaunchAgent and the Spaces handling are macOS-specific. The pipeline needs Apple GPUs and
memory sizes. A Mac App Store build is unlikely: the sandbox makes it hard to run a local model server, spawn
helper processes, and write the wallpaper store used to update every desktop. That leaves direct download, which
means notarisation, an updater and payments all have to be built separately.

**Possible ways around it:** sell outside the App Store (direct download + licence key); keep the runtime tiny and
separate from the builder; consider a Windows runtime later. The live render is plain numpy and OpenCV and would
port easily.

## 7. Small willingness to pay, strong free alternatives

Wallpapers are an impulse purchase. Apple's dynamic wallpapers are free, Wallpaper Engine costs a few dollars, and
there are many free weather-wallpaper apps. Our real advantage is "*your* picture, *your* city, really in sync".
Explaining that takes a demo, and a demo needs a machine most people don't have (see 1).

**Possible ways around it:** a gallery of ready-made scenes for well-known cities as the cheap entry point; the
custom builder as the premium tier; short videos of a day passing in one picture as marketing.

## 8. Costs that are easy to forget

- **Model churn.** Model tags and APIs change (the image library changed versions during development). Every update
  can break generation for everyone.
- **Support.** Every machine is different, every picture is different, and quality is subjective. "My wallpaper looks
  wrong" is hard to debug from a distance.
- **Battery and heat.** The live render is light (about 1 s every 30 min). The build is not. Users will blame the
  app for a hot, loud laptop.
- **Trust.** "Local and private" is a real selling point, but the app still downloads hundreds of gigabytes and runs
  generated code. That code is sandboxed, and the app needs to say so plainly.

## The short version

The technology works end to end, but today it is a power-user tool. Right now it needs a top-end Mac, a developer's
patience, and tolerance for results that are good but not yet great. To sell it, work in this order: **quality
first, then a smaller-model tier, then a one-click app.** Sort out the licences before taking any money.
