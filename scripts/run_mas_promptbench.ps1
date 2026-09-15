[CmdletBinding()]
param(
    [ValidateSet('math','hotpotqa','swe')][string]$Dataset = 'math',
    [ValidateSet('single','independent','sequential','centralized','decentralized')][string]$Topology = 'single',
    [int]$Limit = 10,
    [string]$ModelId = '',
    [string]$Endpoint = '',
    [switch]$Local,
    [string]$TargetPath = 'README.md',
    [switch]$IncludeFullSearch
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

if ($Local) {
    $target = (Resolve-Path (Join-Path $root $TargetPath)).Path
    $output = Join-Path $root ".benchmarks\current-environment-$Dataset-$Topology.json"
    Write-Output "Running local paired rehearsal for $target (no model endpoint)"
    $ablationArgs = @($target, '--backend', 'synthetic', '--seed', '0',
        '--baseline', 'no_skill', '--baseline', 'simple_rewrite', '--baseline', 'focused')
    if ($IncludeFullSearch) { $ablationArgs += @('--baseline', 'full_bcso') }
    $ablationArgs += @('--json-out', $output)
    & python (Join-Path $root 'scripts\run_paired_ablation.py') @ablationArgs
    if ($LASTEXITCODE -ne 0) { throw "Local paired rehearsal failed with exit code $LASTEXITCODE" }
    Write-Output "Wrote rehearsal artifact: $output"
    return
}

$checkout = Join-Path $root 'external\MAS-PromptBench'
$expectedRevision = '1aade2745afd3e8a02d157c00fa9b0c88155aa8b'
if (-not (Test-Path (Join-Path $checkout '.git'))) { throw "Missing external checkout: $checkout" }
$actualRevision = (git -C $checkout rev-parse HEAD).Trim()
if ($actualRevision -ne $expectedRevision) { throw "Unexpected MAS-PromptBench revision: $actualRevision" }
if ([string]::IsNullOrWhiteSpace($ModelId)) { throw 'Set -ModelId to the exact task model identifier before running.' }
if ([string]::IsNullOrWhiteSpace($Endpoint)) { throw 'Set -Endpoint to an OpenAI-compatible endpoint before running.' }
if ($Limit -lt 1) { throw 'Limit must be positive.' }

$env:MODEL_ID = $ModelId
$env:VLLM_BASE_URL = $Endpoint
$env:PYTHONPATH = if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $checkout
} else {
    "$checkout;$($env:PYTHONPATH)"
}
Push-Location $checkout
try {
    $runner = Join-Path 'topologies' $Topology
    $script = Get-ChildItem $runner -Recurse -Filter "*_$Dataset.py" | Select-Object -First 1
    if ($null -eq $script) { throw "No upstream runner found for $Topology/$Dataset" }
    Write-Output "Running MAS-PromptBench $Dataset/$Topology at $actualRevision (limit=$Limit)"
    python $script.FullName --batch --limit $Limit
} finally {
    Pop-Location
}
