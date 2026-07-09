def redo_current_spike_summary(current_summary_df: pd.DataFrame,
                               master_path: str = MASTER_CSV,
                               source_label: str = RUN_ID,
                               run_ts: str = RUN_TS) -> pd.DataFrame:
    """
    Reduce totals by the *current* summary table by appending its negative to the master CSV.
    Does not delete history; keeps an audit trail.

    current_summary_df: the DataFrame you just created (e.g., `spike_summary`)
    """
    # Copy and ensure expected columns exist
    neg = current_summary_df.copy()
    neg["ROI"] = neg["ROI"].astype(str)
    for col in ["n_spikes_all", "n_spikes_in_stim", "n_spikes_outside"]:
        if col not in neg.columns:
            neg[col] = 0
        neg[col] = pd.to_numeric(neg[col], errors="coerce").fillna(0).astype(int) * -1

    # Mark metadata
    neg.insert(0, "source", source_label)
    neg.insert(1, "run_timestamp", run_ts)
    neg.insert(2, "op", "redo_subtract")  # optional audit flag

    # Append (align schema if needed)
    if Path(master_path).exists():
        master = pd.read_csv(master_path)
        all_cols = list(dict.fromkeys(list(master.columns) + list(neg.columns)))
        master = master.reindex(columns=all_cols)
        neg = neg.reindex(columns=all_cols)
        master = pd.concat([master, neg], ignore_index=True)
    else:
        master = neg

    master.to_csv(master_path, index=False)
    return master

# ---- Use it whenever you want to redo THIS run's summary ----
# This subtracts the current table from your accumulated totals:
master_df = redo_current_spike_summary(spike_summary, master_path=MASTER_CSV, source_label=RUN_ID, run_ts=RUN_TS)

# Recompute totals CSV after redo (optional but handy)
totals_df = summarize_totals(MASTER_CSV)
totals_df.to_csv("roi_spike_totals_across_runs.csv", index=False)
print("Redo applied. Totals updated.")