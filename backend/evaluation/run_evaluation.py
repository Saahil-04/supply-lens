"""Run SupplyLens over a list of repositories and produce the evaluation tables.

    python -m evaluation.run_evaluation evaluation/repos.txt            # analyze + summarize
    python -m evaluation.run_evaluation --score evaluation/out/validation_sample.csv   # after manual labelling

Needs network access and GITHUB_TOKEN in .env (5,000 requests/hour; each repo uses ~100-800).
"""
import asyncio
import json
import sys
from pathlib import Path

from app.analysis.service import analyze_repository
from app.errors import AnalysisError
from evaluation.evaluate import FINDING_COLUMNS, flatten, read_csv, sample_for_validation, score_validation, summarize, write_csv

OUT = Path("evaluation/out")


async def run(repos_file: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    urls = [line.strip() for line in Path(repos_file).read_text().splitlines() if line.strip() and not line.startswith("#")]
    all_rows, per_repo, failures = [], [], []
    for url in urls:
        name = "/".join(url.rstrip("/").split("/")[-2:])
        print(f"[{len(per_repo) + len(failures) + 1}/{len(urls)}] {name} ...", flush=True)
        try:
            result = await analyze_repository(url)
        except AnalysisError as exc:
            failures.append({"repo": name, "code": exc.code, "message": exc.message})
            print(f"   FAILED {exc.code}: {exc.message}")
            if exc.code == "GITHUB_RATE_LIMITED":
                print("   Rate limited: stop here, wait for the reset, and re-run with the remaining repos.")
                break
            continue
        except Exception as exc:                                  # keep going; record the failure
            failures.append({"repo": name, "code": "ERROR", "message": str(exc)})
            continue
        (OUT / f"{name.replace('/', '__')}.json").write_text(json.dumps(result, default=str))
        rows = flatten(result, name)
        all_rows.extend(rows)
        meta = result["analysis_metadata"]
        per_repo.append({"repo": name, "status": meta["vulnerability_analysis_status"], "packages": result["summary"]["total_packages"],
                         "seconds": round(meta["timings_ms"]["total"] / 1000, 1), **summarize(rows)})
        print(f"   {len(rows)} findings, status={meta['vulnerability_analysis_status']}, {per_repo[-1]['seconds']}s")
    write_csv(str(OUT / "findings.csv"), all_rows, FINDING_COLUMNS)
    write_csv(str(OUT / "validation_sample.csv"), sample_for_validation(all_rows), FINDING_COLUMNS + ["manual_label"])
    overall = summarize(all_rows)
    (OUT / "summary.json").write_text(json.dumps({"overall": overall, "per_repo": per_repo, "failures": failures}, indent=2))
    print("\nOVERALL:", json.dumps(overall, indent=2))
    print(f"\nWrote {OUT}/findings.csv, summary.json, validation_sample.csv")
    print("Next: open validation_sample.csv, fill manual_label (used / not_used / unsure), then run with --score.")


def score(path: str) -> None:
    print(json.dumps(score_validation(read_csv(path)), indent=2))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--score":
        score(sys.argv[2])
    elif len(sys.argv) == 2:
        asyncio.run(run(sys.argv[1]))
    else:
        sys.exit(__doc__)
