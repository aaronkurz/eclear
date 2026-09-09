/** The columns `create_case_log` always produces. Nothing to configure — the
 *  pane exists so the catalog accounts for every column in the schema rail. */
export default function BasePane({ columns }: { columns: string[] }) {
    return (
        <div className="en-pane">
            <div className="en-pane-sub">Always present</div>
            <div className="en-chips">
                {columns.map((column) => (
                    <span className="en-chip en-applied" key={column}>
                        {column}
                    </span>
                ))}
            </div>
        </div>
    );
}
