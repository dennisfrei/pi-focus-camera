<script lang="ts">
  // A guide to what each control does and how to use it at the telescope. Kept in sync with the
  // actual settings the app exposes (exposure/gain/AE/AWB, preview modes, focus metrics, ROI/zoom).
  let { open = $bindable(false) }: { open?: boolean } = $props()

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape') open = false
  }
</script>

<svelte:window onkeydown={onKey} />

{#if open}
  <div
    class="backdrop"
    role="button"
    tabindex="-1"
    aria-label="Close help"
    onclick={() => (open = false)}
    onkeydown={(e) => e.key === 'Enter' && (open = false)}
  ></div>

  <div class="modal" role="dialog" aria-modal="true" aria-label="Help — how to use the camera">
    <header>
      <h2>How to use it</h2>
      <button class="close" aria-label="Close" onclick={() => (open = false)}>✕</button>
    </header>

    <div class="body">
      <p class="lead">
        A quick tour of every control. The short version: <b>lock exposure and gain</b>, switch to
        <b>Star</b> preview so faint stars appear, drag a box over one star, then turn the focuser to
        make the <b>focus number</b> peak.
      </p>

      <section>
        <h3>Preview mode</h3>
        <dl>
          <dt>Normal</dt>
          <dd>
            Fast video preview (~30 fps). Right for the <b>Moon, planets, and daytime</b> — bright
            targets that show up at short exposures.
          </dd>
          <dt>Star</dt>
          <dd>
            Long-exposure preview: each frame is held open for up to a couple of seconds, so faint
            <b>stars actually become visible</b>. The stream slows to about 1 frame/second — that's
            expected. Use this for focusing on the sky. A normal 30 fps preview gives each frame only
            ~33 ms, and almost every star is invisible at that speed.
          </dd>
        </dl>
      </section>

      <section>
        <h3>Exposure &amp; gain</h3>
        <dl>
          <dt>Auto exposure (AE)</dt>
          <dd>
            When on, the camera picks the exposure and gain for you. <b>Turn it off before focusing
            on stars.</b> As a star drifts out of focus it dims, and auto-exposure keeps brightening
            the frame to compensate — which fools the focus meter. Manual, locked exposure is what
            makes the metric trustworthy.
          </dd>
          <dt>Auto white balance (AWB)</dt>
          <dd>
            Auto colour balance. Turn it off for consistent frames — colour shifting between shots
            isn't useful for astronomy and, like AE, adds a moving variable while you focus.
          </dd>
          <dt>Exposure</dt>
          <dd>
            How long the sensor collects light, from microseconds up to the sensor's maximum (the
            slider's range comes from the attached sensor — e.g. the V2 module tops out near 11.8 s).
            Longer = brighter and reveals fainter stars, but too long saturates bright stars and, on
            a tracking mount, risks trailing.
          </dd>
          <dt>Gain (ISO)</dt>
          <dd>
            Amplifies the signal <i>after</i> exposure — it brightens the image without a longer
            exposure, which keeps the preview responsive, but it also amplifies <b>noise</b>. Raise
            it to see stars while focusing; lower it for cleaner captures.
          </dd>
        </dl>
      </section>

      <section>
        <h3>Focus assist</h3>
        <dl>
          <dt>Scene mode</dt>
          <dd>
            A sharpness score (variance of the Laplacian) — <b>higher is better</b>. Great on
            detailed targets like the Moon or planets. Unreliable on a lone star, where sensor noise
            itself looks like fine detail.
          </dd>
          <dt>Star mode <span class="tag">night default</span></dt>
          <dd>
            Measures the <b>brightest star</b> in your region two ways:
            <ul>
              <li>
                <b>HFD</b> (half-flux diameter) — the width of the star in pixels, specifically the
                diameter that contains half its light. It <b>shrinks as you approach focus</b>, so
                you turn the focuser to make the number as <b>small</b> as possible. This is the
                same measure SharpCap and NINA use.
              </li>
              <li><b>Peak</b> — the brightness of the star's core. It <b>rises</b> toward focus.</li>
            </ul>
          </dd>
          <dt>The bar &amp; graph</dt>
          <dd>
            The bar always means <b>fuller = better focus</b>, whichever metric you're using. The
            graph is the recent trend — watch it move as you rack the focuser. In Star mode it shows
            "no star in the region" until you point at (or box) an actual star.
          </dd>
        </dl>
      </section>

      <section>
        <h3>Framing tools</h3>
        <dl>
          <dt>ROI (drag a box)</dt>
          <dd>
            Drag a rectangle on the preview to restrict the focus measurement to that region — put
            it over a <b>single star</b> for the cleanest HFD reading. "Clear ROI" goes back to the
            whole frame.
          </dd>
          <dt>Zoom</dt>
          <dd>
            Magnifies your region for critical focus. On the real camera this is a <b>true 1:1
            sensor crop</b> (actual pixels, labelled "Zoom 1:1"); on the mock it's a plain digital
            zoom of the preview.
          </dd>
          <dt>Grid &amp; crosshair</dt>
          <dd>Rule-of-thirds grid and a centre crosshair for framing and centring a target.</dd>
        </dl>
      </section>

      <section>
        <h3>Histogram</h3>
        <p>
          The spread of brightness across the frame, on a <b>log scale</b> (a linear one collapses on
          a dark sky). Most pixels sit at the dark end; a tail to the right is your stars. A
          <b>clipping warning</b> appears when highlights are blown out — back off exposure or gain
          if you see it on stars you care about.
        </p>
      </section>

      <section>
        <h3>Presets &amp; night mode</h3>
        <dl>
          <dt>Presets</dt>
          <dd>
            Save the current exposure/gain/mode bundle under a name (e.g. "Moon", "Star focus") and
            reload it in one tap. Presets are stored on the Pi and survive a restart.
          </dd>
          <dt>Night mode</dt>
          <dd>
            The red-on-black theme (toggle top-right) preserves your dark adaptation at the eyepiece.
            Switch to the normal theme indoors.
          </dd>
        </dl>
      </section>
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: color-mix(in srgb, #000 70%, transparent);
    z-index: 20;
    border: none;
  }
  .modal {
    position: fixed;
    z-index: 21;
    inset: 0;
    margin: auto;
    width: min(640px, 92vw);
    max-height: 85vh;
    display: flex;
    flex-direction: column;
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 12px;
    box-shadow: 0 10px 40px color-mix(in srgb, #000 60%, transparent);
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.9rem 1.1rem;
    border-bottom: 1px solid var(--line);
  }
  h2 {
    margin: 0;
    font-size: 1.05rem;
  }
  .close {
    background: transparent;
    color: var(--fg);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 0.25rem 0.55rem;
    cursor: pointer;
    font-size: 0.85rem;
  }
  .body {
    overflow-y: auto;
    padding: 1rem 1.1rem 1.3rem;
  }
  .lead {
    margin: 0 0 1rem;
    color: var(--fg);
    font-size: 0.92rem;
    line-height: 1.5;
  }
  section {
    margin-top: 1.1rem;
    padding-top: 0.9rem;
    border-top: 1px solid color-mix(in srgb, var(--line) 60%, transparent);
  }
  h3 {
    margin: 0 0 0.5rem;
    font-size: 0.9rem;
    color: var(--accent);
    letter-spacing: 0.02em;
  }
  dl {
    margin: 0;
  }
  dt {
    font-weight: 600;
    font-size: 0.86rem;
    margin-top: 0.6rem;
  }
  dd {
    margin: 0.15rem 0 0;
    color: var(--muted);
    font-size: 0.84rem;
    line-height: 1.5;
  }
  dd b {
    color: var(--fg);
    font-weight: 600;
  }
  p {
    color: var(--muted);
    font-size: 0.84rem;
    line-height: 1.5;
    margin: 0;
  }
  ul {
    margin: 0.3rem 0 0;
    padding-left: 1.1rem;
  }
  li {
    margin: 0.3rem 0;
  }
  .tag {
    font-size: 0.68rem;
    color: var(--accent);
    border: 1px solid color-mix(in srgb, var(--accent) 50%, transparent);
    border-radius: 6px;
    padding: 0.02rem 0.35rem;
    margin-left: 0.35rem;
    vertical-align: middle;
    font-weight: 500;
  }
</style>
