/**
 * Prompt A/B Diff Tester — Frontend logic
 * Handles form submission, API calls, result rendering, and error states.
 */

(function () {
  'use strict';

  // --- DOM refs ---
  const form = document.getElementById('compare-form');
  const btn = document.getElementById('btn-compare');
  const errorBanner = document.getElementById('error-banner');
  const resultsSection = document.getElementById('results-section');
  const outputA = document.getElementById('output-a');
  const outputB = document.getElementById('output-b');
  const metaA = document.getElementById('meta-a');
  const metaB = document.getElementById('meta-b');
  const varianceA = document.getElementById('variance-a');
  const varianceB = document.getElementById('variance-b');
  const sysInstructionToggle = document.getElementById('use-system-instruction');
  const runsInput = document.getElementById('runs-count');

  // --- Helpers ---

  /** Show or hide the error banner. */
  function showError(message) {
    errorBanner.textContent = message;
    errorBanner.classList.add('visible');
  }

  function hideError() {
    errorBanner.classList.remove('visible');
    errorBanner.textContent = '';
  }

  /** Set button to loading or idle state. */
  function setLoading(isLoading) {
    btn.disabled = isLoading;
    btn.classList.toggle('loading', isLoading);
  }

  /** Build metadata badges for a result. */
  function renderMeta(container, result) {
    container.innerHTML = '';
    const badges = [
      { label: 'Input tokens', value: result.input_tokens },
      { label: 'Output tokens', value: result.output_tokens },
      { label: 'Latency', value: result.latency_ms + ' ms' },
      { label: 'Cost', value: '$' + result.estimated_cost.toFixed(4) },
    ];
    badges.forEach(({ label, value }) => {
      const badge = document.createElement('span');
      badge.className = 'meta-badge';
      badge.innerHTML =
        label + '&nbsp;<span class="meta-value">' + escapeHtml(String(value)) + '</span>';
      container.appendChild(badge);
    });
  }

  /** Render variance summary badges. */
  function renderVariance(container, variance) {
    container.innerHTML = '';
    if (!variance) return;

    const badges = [
      { label: 'Runs', value: variance.run_count },
      { label: 'Length range', value: variance.output_length_min + '–' + variance.output_length_max + ' chars' },
      { label: 'Spread', value: variance.output_length_range + ' chars' },
      { label: 'Identical?', value: variance.outputs_identical ? 'Yes' : 'No' },
      { label: 'Total cost', value: '$' + variance.total_cost.toFixed(4) },
    ];
    badges.forEach(({ label, value }) => {
      const badge = document.createElement('span');
      badge.className = 'meta-badge variance-badge';
      badge.innerHTML =
        label + '&nbsp;<span class="meta-value">' + escapeHtml(String(value)) + '</span>';
      container.appendChild(badge);
    });
  }

  /** Minimal HTML escape for text content. */
  function escapeHtml(str) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  /** Render a single result card. */
  function renderResult(outputEl, metaEl, result) {
    outputEl.textContent = result.output;
    renderMeta(metaEl, result);
  }

  // --- Form submit ---

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    hideError();

    const promptA = document.getElementById('prompt-a').value.trim();
    const promptB = document.getElementById('prompt-b').value.trim();
    const testInput = document.getElementById('test-input').value.trim();
    const runs = parseInt(runsInput.value, 10) || 1;

    // Client-side validation
    if (!promptA || !promptB || !testInput) {
      showError('All fields are required. Please fill in Prompt A, Prompt B, and Test Input.');
      return;
    }

    setLoading(true);
    resultsSection.classList.remove('visible');

    const payload = {
      prompt_a: promptA,
      prompt_b: promptB,
      test_input: testInput,
      use_system_instruction: sysInstructionToggle.checked,
      runs: Math.max(1, Math.min(5, runs)),
    };

    try {
      const response = await fetch('/api/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        showError(data.error || 'An unexpected error occurred (HTTP ' + response.status + ').');
        return;
      }

      // Render results (first run or only run)
      renderResult(outputA, metaA, data.result_a);
      renderResult(outputB, metaB, data.result_b);

      // Render variance if multi-run
      renderVariance(varianceA, data.variance_a || null);
      renderVariance(varianceB, data.variance_b || null);

      resultsSection.classList.add('visible');

    } catch (err) {
      showError('Network error — could not reach the server. Is it running?');
    } finally {
      setLoading(false);
    }
  });
})();
