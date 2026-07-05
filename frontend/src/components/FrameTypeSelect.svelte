<script lang="ts">
  import type { FrameType } from '../lib/api'

  // Light / dark / flat / bias — recorded with each capture for the stacking pipeline.
  let { value = $bindable('light') }: { value?: FrameType } = $props()
</script>

<select bind:value class="ftype" aria-label="Frame type">
  <option value="light">Light</option>
  <option value="dark">Dark</option>
  <option value="flat">Flat</option>
  <option value="bias">Bias</option>
</select>

<style>
  .ftype {
    background: transparent;
    color: var(--fg);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 0.35rem 0.4rem;
    font-size: 0.82rem;
    cursor: pointer;
  }
  .ftype option {
    background: var(--bg);
    color: var(--fg);
  }
</style>
