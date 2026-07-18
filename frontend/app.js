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
  const enableJudgeToggle = document.getElementById('enable-judge');

  // New DOM refs for Diff and Run selectors
  const runSelectors = document.getElementById('run-selectors');
  const selectRunA = document.getElementById('select-run-a');
  const selectRunB = document.getElementById('select-run-b');
  const toggleDiff = document.getElementById('toggle-diff');

  // LLM Judge DOM refs
  const judgeCard = document.getElementById('judge-card');
  const judgeBadge = document.getElementById('judge-badge');
  const judgeReasoning = document.getElementById('judge-reasoning');

  // --- App State ---
  let lastCompareData = null;

  // --- Helpers ---

  /** Compute word-level differences between textA and textB.
   * Returns an array of diff objects: { type: 'equal'|'added'|'removed', text: string }
   */
  function computeDiff(textA, textB) {
    const wordsA = textA.split(/(\s+)/);
    const wordsB = textB.split(/(\s+)/);
    
    const N = wordsA.length;
    const M = wordsB.length;
    
    const dp = Array.from({ length: N + 1 }, () => new Int32Array(M + 1));
    
    for (let i = 1; i <= N; i++) {
      for (let j = 1; j <= M; j++) {
        if (wordsA[i - 1] === wordsB[j - 1]) {
          dp[i][j] = dp[i - 1][j - 1] + 1;
        } else {
          dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
        }
      }
    }
    
    let i = N;
    let j = M;
    const diff = [];
    
    while (i > 0 || j > 0) {
      if (i > 0 && j > 0 && wordsA[i - 1] === wordsB[j - 1]) {
        diff.push({ type: 'equal', text: wordsA[i - 1] });
        i--;
        j--;
      } else if (j > 0 && (i === 0 || dp[i - 1][j] < dp[i][j - 1])) {
        diff.push({ type: 'added', text: wordsB[j - 1] });
        j--;
      } else if (i > 0 && (j === 0 || dp[i - 1][j] >= dp[i][j - 1])) {
        diff.push({ type: 'removed', text: wordsA[i - 1] });
        i--;
      }
    }
    
    return diff.reverse();
  }

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

  /** Populate the run selection dropdowns if runs > 1. */
  function populateRunDropdowns(runsCount) {
    selectRunA.innerHTML = '';
    selectRunB.innerHTML = '';

    if (runsCount > 1) {
      for (let i = 0; i < runsCount; i++) {
        const optA = document.createElement('option');
        optA.value = i;
        optA.textContent = 'Run ' + (i + 1);
        selectRunA.appendChild(optA);

        const optB = document.createElement('option');
        optB.value = i;
        optB.textContent = 'Run ' + (i + 1);
        selectRunB.appendChild(optB);
      }
      runSelectors.style.display = 'flex';
    } else {
      runSelectors.style.display = 'none';
    }
  }

  /** Update the UI display based on the selected runs and diff toggle state. */
  function updateResultsDisplay() {
    if (!lastCompareData) return;

    const showDiff = toggleDiff.checked;
    const runsCount = lastCompareData.runs_a ? lastCompareData.runs_a.length : 1;

    let resultA = lastCompareData.result_a;
    let resultB = lastCompareData.result_b;

    let idxA = 0;
    let idxB = 0;
    if (runsCount > 1) {
      idxA = parseInt(selectRunA.value, 10) || 0;
      idxB = parseInt(selectRunB.value, 10) || 0;
      resultA = lastCompareData.runs_a[idxA];
      resultB = lastCompareData.runs_b[idxB];
    }

    console.log("[DiffTester] updateResultsDisplay called:", {
      showDiff,
      runsCount,
      idxA,
      idxB,
      lengthA: resultA.output.length,
      lengthB: resultB.output.length
    });

    if (showDiff) {
      const diffs = computeDiff(resultA.output, resultB.output);
      console.log("[DiffTester] Computed diff chunks count:", diffs.length);

      // Render Prompt A output (only keep equal and removed tokens)
      let htmlA = '';
      diffs.forEach(part => {
        if (part.type === 'equal') {
          htmlA += escapeHtml(part.text);
        } else if (part.type === 'removed') {
          htmlA += '<span class="diff-removed">' + escapeHtml(part.text) + '</span>';
        }
      });
      outputA.innerHTML = htmlA;

      // Render Prompt B output (only keep equal and added tokens)
      let htmlB = '';
      diffs.forEach(part => {
        if (part.type === 'equal') {
          htmlB += escapeHtml(part.text);
        } else if (part.type === 'added') {
          htmlB += '<span class="diff-added">' + escapeHtml(part.text) + '</span>';
        }
      });
      outputB.innerHTML = htmlB;
    } else {
      outputA.textContent = resultA.output;
      outputB.textContent = resultB.output;
    }

    // Render metadata badges for the selected run pair
    renderMeta(metaA, resultA);
    renderMeta(metaB, resultB);

    // Render variance if multi-run (always visible if runs > 1, independent of diff toggle)
    renderVariance(varianceA, lastCompareData.variance_a || null);
    renderVariance(varianceB, lastCompareData.variance_b || null);

    // Render LLM Judge Verdict if present
    if (lastCompareData.judge_verdict) {
      const verdict = lastCompareData.judge_verdict;
      judgeBadge.textContent = 'Winner: ' + verdict.choice;
      judgeBadge.className = 'judge-badge'; // reset classes
      if (verdict.choice === 'A') {
        judgeBadge.classList.add('choice-a');
      } else if (verdict.choice === 'B') {
        judgeBadge.classList.add('choice-b');
      } else {
        judgeBadge.classList.add('choice-tie');
        judgeBadge.textContent = verdict.choice; // e.g. "Tie" or custom fail message
      }

      judgeReasoning.textContent = verdict.reasoning;
      judgeCard.style.display = 'block';
    } else {
      judgeCard.style.display = 'none';
    }
  }

  // --- Event Listeners ---
  toggleDiff.addEventListener('change', updateResultsDisplay);
  selectRunA.addEventListener('change', updateResultsDisplay);
  selectRunB.addEventListener('change', updateResultsDisplay);

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
      enable_judge: enableJudgeToggle.checked,
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

      // Store response data and populate UI controls
      lastCompareData = data;
      const runsCount = data.runs_a ? data.runs_a.length : 1;
      populateRunDropdowns(runsCount);

      // Trigger initial results display
      updateResultsDisplay();
      resultsSection.classList.add('visible');

    } catch (err) {
      showError('Network error — could not reach the server. Is it running?');
    } finally {
      setLoading(false);
    }
  });
})();
