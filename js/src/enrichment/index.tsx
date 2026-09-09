import * as React from "react";
import { useModelState, createRender } from "@anywidget/react";
import App from "./App";
import { normalizeCatalog, normalizeSpecs, normalizeSummary } from "./data";
import { normalizeEventCatalog, normalizeEventSpecs, toRawEventSpec } from "./event/data";
import { EMPTY_EVENT_STAGING } from "./event/staging";
import type { EventStaging } from "./event/staging";
import type {
    EventApplyResult,
    EventPreviewResult,
    RawEventCatalog,
    RawEventSpec,
} from "./event/types";
import { EMPTY_STAGING, toRawSpec } from "./staging";
import type { Staging } from "./staging";
import type {
    ApplyResult,
    PreviewResult,
    RawCatalog,
    RawLogSummary,
    RawSpec,
} from "./types";

const TOAST_MS = 2600;

/** A toast that clears itself, shared by both tabs' request cycles. */
function useFlash(): [string | null, (message: string) => void] {
    const [toast, setToast] = React.useState<string | null>(null);
    const timer = React.useRef<ReturnType<typeof setTimeout> | null>(null);
    const flash = React.useCallback((message: string) => {
        setToast(message);
        if (timer.current) clearTimeout(timer.current);
        timer.current = setTimeout(() => setToast(null), TOAST_MS);
    }, []);
    React.useEffect(
        () => () => {
            if (timer.current) clearTimeout(timer.current);
        },
        [],
    );
    return [toast, flash];
}

function Widget() {  // eslint-disable-line max-lines-per-function
    const [title] = useModelState<string>("title");
    const [rawSummary] = useModelState<RawLogSummary>("log_summary");
    const [rawCatalog] = useModelState<RawCatalog>("catalog");
    const [rawApplied] = useModelState<RawSpec[]>("applied");
    const [, setApplyRequest] = useModelState<Record<string, unknown>>("apply_request");
    const [applyResult] = useModelState<ApplyResult>("apply_result");
    const [, setPreviewRequest] = useModelState<Record<string, unknown>>("preview_request");
    const [previewResult] = useModelState<PreviewResult>("preview_result");

    const [rawEventCatalog] = useModelState<RawEventCatalog>("event_catalog");
    const [rawEventApplied] = useModelState<RawEventSpec[]>("event_applied");
    const [, setEventApplyRequest] =
        useModelState<Record<string, unknown>>("event_apply_request");
    const [eventApplyResult] = useModelState<EventApplyResult>("event_apply_result");
    const [, setEventPreviewRequest] =
        useModelState<Record<string, unknown>>("event_preview_request");
    const [eventPreviewResult] = useModelState<EventPreviewResult>("event_preview_result");

    const summary = React.useMemo(() => normalizeSummary(rawSummary), [rawSummary]);
    const catalog = React.useMemo(() => normalizeCatalog(rawCatalog), [rawCatalog]);
    const applied = React.useMemo(() => normalizeSpecs(rawApplied), [rawApplied]);
    const eventCatalog = React.useMemo(
        () => normalizeEventCatalog(rawEventCatalog),
        [rawEventCatalog],
    );
    const eventApplied = React.useMemo(
        () => normalizeEventSpecs(rawEventApplied),
        [rawEventApplied],
    );

    const [staging, setStaging] = React.useState<Staging>(EMPTY_STAGING);
    const [applying, setApplying] = React.useState(false);
    const [error, setError] = React.useState<string | null>(null);
    const [toast, flash] = useFlash();
    const [previewOpen, setPreviewOpen] = React.useState(false);
    const [previewPending, setPreviewPending] = React.useState(false);
    const [preview, setPreview] = React.useState<PreviewResult | null>(null);

    const [eventStaging, setEventStaging] = React.useState<EventStaging>(EMPTY_EVENT_STAGING);
    const [eventApplying, setEventApplying] = React.useState(false);
    const [eventError, setEventError] = React.useState<string | null>(null);
    const [eventToast, eventFlash] = useFlash();
    const [blocked, setBlocked] = React.useState<
        { column: string; used_by: string[] }[] | null
    >(null);
    const [eventPreviewOpen, setEventPreviewOpen] = React.useState(false);
    const [eventPreviewPending, setEventPreviewPending] = React.useState(false);
    const [eventPreview, setEventPreview] = React.useState<EventPreviewResult | null>(null);
    const [eventPreviewScope, setEventPreviewScope] = React.useState("touching");

    const applyIdRef = React.useRef(0);
    const lastApplyIdRef = React.useRef<number | null>(null);
    const previewIdRef = React.useRef(0);
    const lastPreviewIdRef = React.useRef<number | null>(null);
    const seedRef = React.useRef(0);
    const eventApplyIdRef = React.useRef(0);
    const lastEventApplyIdRef = React.useRef<number | null>(null);
    const eventPreviewIdRef = React.useRef(0);
    const lastEventPreviewIdRef = React.useRef<number | null>(null);
    const eventSeedRef = React.useRef(0);

    // Receive the result of an apply. Staging is cleared only on success: a
    // failed apply must leave the user's selection intact to fix or discard.
    React.useEffect(() => {
        if (!applyResult || applyResult.request_id == null) return;
        if (applyResult.request_id === lastApplyIdRef.current) return;
        lastApplyIdRef.current = applyResult.request_id;
        setApplying(false);
        if (applyResult.ok) {
            setStaging(EMPTY_STAGING);
            setError(null);
            flash(`Applied ✓ ${delta(applyResult.added, applyResult.removed)} · ${applyResult.columns ?? 0} columns`);
        } else {
            setError(applyResult.error ?? "apply failed");
        }
    }, [applyResult, flash]);

    React.useEffect(() => {
        if (!previewResult || previewResult.request_id == null) return;
        if (previewResult.request_id === lastPreviewIdRef.current) return;
        lastPreviewIdRef.current = previewResult.request_id;
        setPreviewPending(false);
        setPreview(previewResult);
    }, [previewResult]);

    // The event side has a third outcome besides ok and failed: a removal Python
    // refused because something reads the column. That is not an error to fix in
    // the staging area, so it gets its own banner rather than the inline slot.
    React.useEffect(() => {
        if (!eventApplyResult || eventApplyResult.request_id == null) return;
        if (eventApplyResult.request_id === lastEventApplyIdRef.current) return;
        lastEventApplyIdRef.current = eventApplyResult.request_id;
        setEventApplying(false);
        if (eventApplyResult.ok) {
            setEventStaging(EMPTY_EVENT_STAGING);
            setEventError(null);
            setBlocked(null);
            eventFlash(
                `Applied ✓ ${delta(eventApplyResult.added, eventApplyResult.removed)} · ${eventApplyResult.columns ?? 0} columns`,
            );
        } else if (eventApplyResult.blocked?.length) {
            setBlocked(eventApplyResult.blocked);
            setEventError(null);
        } else {
            setEventError(eventApplyResult.error ?? "apply failed");
        }
    }, [eventApplyResult, eventFlash]);

    React.useEffect(() => {
        if (!eventPreviewResult || eventPreviewResult.request_id == null) return;
        if (eventPreviewResult.request_id === lastEventPreviewIdRef.current) return;
        lastEventPreviewIdRef.current = eventPreviewResult.request_id;
        setEventPreviewPending(false);
        setEventPreview(eventPreviewResult);
    }, [eventPreviewResult]);

    const requestApply = React.useCallback(() => {
        if (applying) return;
        setApplying(true);
        setError(null);
        applyIdRef.current += 1;
        setApplyRequest({
            add: staging.add.map(toRawSpec),
            remove: staging.remove,
            request_id: applyIdRef.current,
        });
    }, [applying, staging, setApplyRequest]);

    // One handler for both opening the preview and resampling it: each call
    // advances the seed, so "Resample" is just another request.
    const requestPreview = React.useCallback(() => {
        setPreviewOpen(true);
        setPreviewPending(true);
        previewIdRef.current += 1;
        seedRef.current += 1;
        setPreviewRequest({
            add: staging.add.map(toRawSpec),
            remove: staging.remove,
            seed: seedRef.current,
            request_id: previewIdRef.current,
        });
    }, [staging, setPreviewRequest]);

    const requestEventApply = React.useCallback(() => {
        if (eventApplying) return;
        setEventApplying(true);
        setEventError(null);
        setBlocked(null);
        eventApplyIdRef.current += 1;
        setEventApplyRequest({
            add: eventStaging.add.map(toRawEventSpec),
            remove: eventStaging.remove,
            request_id: eventApplyIdRef.current,
        });
    }, [eventApplying, eventStaging, setEventApplyRequest]);

    const requestEventPreview = React.useCallback(
        (scope: string) => {
            setEventPreviewOpen(true);
            setEventPreviewPending(true);
            eventPreviewIdRef.current += 1;
            eventSeedRef.current += 1;
            setEventPreviewRequest({
                add: eventStaging.add.map(toRawEventSpec),
                remove: eventStaging.remove,
                seed: eventSeedRef.current,
                scope,
                request_id: eventPreviewIdRef.current,
            });
        },
        [eventStaging, setEventPreviewRequest],
    );

    return (
        <App
            title={title || "Log enrichment"}
            summary={summary}
            caseSide={{
                catalog,
                applied,
                staging,
                onStagingChange: setStaging,
                applying,
                error,
                toast,
                onApply: requestApply,
                preview,
                previewPending,
                onPreview: requestPreview,
                previewOpen,
                onClosePreview: () => setPreviewOpen(false),
            }}
            eventSide={{
                catalog: eventCatalog,
                applied: eventApplied,
                baseColumnCount: Math.max(
                    eventCatalog.columns.length - eventApplied.length,
                    0,
                ),
                staging: eventStaging,
                onStagingChange: setEventStaging,
                applying: eventApplying,
                error: eventError,
                toast: eventToast,
                onApply: requestEventApply,
                blocked,
                onDismissBlocked: () => setBlocked(null),
                preview: eventPreview,
                previewPending: eventPreviewPending,
                onPreview: () => requestEventPreview(eventPreviewScope),
                previewOpen: eventPreviewOpen,
                onClosePreview: () => setEventPreviewOpen(false),
                previewScope: eventPreviewScope,
                onPreviewScope: (scope: string) => {
                    setEventPreviewScope(scope);
                    requestEventPreview(scope);
                },
            }}
        />
    );
}

function delta(added?: string[], removed?: string[]): string {
    const parts: string[] = [];
    if (added?.length) parts.push(`+${added.length}`);
    if (removed?.length) parts.push(`−${removed.length}`);
    return parts.join(" / ");
}

export default {
    render: createRender(Widget),
};
