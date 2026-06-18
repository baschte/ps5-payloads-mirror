import { useCallback, useEffect, useState } from 'react';
import {
    getGitStatus,
    getTitle,
    gitPush,
    listPayloads,
    setTitle,
    updateAll,
} from './api';
import { AddMirrorForm } from './components/AddMirrorForm';
import { PayloadTable } from './components/PayloadTable';
import { SchedulerPanel } from './components/SchedulerPanel';
import { Toast } from './components/Toast';
import type { ToastMessage } from './components/Toast';
import {
    IconCheck,
    IconExternal,
    IconMoon,
    IconPencil,
    IconSun,
    IconSync,
    IconUpload,
    IconX,
    Logo,
} from './components/icons';
import { useTheme } from './useTheme';
import type { Payload } from './types';

export function App() {
    const [payloads, setPayloads] = useState<Payload[]>([]);
    const [loading, setLoading] = useState(true);
    const [updatingAll, setUpdatingAll] = useState(false);
    const [busyName, setBusyName] = useState<string | null>(null);
    const [toast, setToast] = useState<ToastMessage | null>(null);
    const [gitEnabled, setGitEnabled] = useState(false);
    const [publishing, setPublishing] = useState(false);
    const [title, setTitleState] = useState('');
    const [editingTitle, setEditingTitle] = useState(false);
    const [titleDraft, setTitleDraft] = useState('');
    const [savingTitle, setSavingTitle] = useState(false);
    const { theme, toggle: toggleTheme } = useTheme();

    const notify = useCallback((kind: ToastMessage['kind'], text: string) => {
        setToast({ kind, text });
    }, []);

    // Effect: synchronize local list with the backend on mount (external system).
    const refresh = useCallback(async () => {
        setLoading(true);
        try {
            setPayloads(await listPayloads());
        } catch (err) {
            notify(
                'error',
                err instanceof Error ? err.message : 'Failed to load mirrors.'
            );
        } finally {
            setLoading(false);
        }
    }, [notify]);

    useEffect(() => {
        void refresh();
    }, [refresh]);

    // Effect: check once whether the git-publish feature is configured.
    useEffect(() => {
        getGitStatus()
            .then((s) => setGitEnabled(s.enabled))
            .catch(() => setGitEnabled(false));
    }, []);

    // Effect: load the collection title on mount.
    useEffect(() => {
        getTitle()
            .then((t) => setTitleState(t.name))
            .catch(() => setTitleState(''));
    }, []);

    async function saveTitle() {
        const next = titleDraft.trim();
        if (!next) {
            setEditingTitle(false);
            return;
        }
        setSavingTitle(true);
        try {
            const saved = await setTitle(next);
            setTitleState(saved.name);
            setEditingTitle(false);
            notify('success', 'Title updated.');
        } catch (err) {
            notify(
                'error',
                err instanceof Error ? err.message : 'Failed to update title.'
            );
        } finally {
            setSavingTitle(false);
        }
    }

    const anyBusy = updatingAll || busyName !== null || publishing;

    async function handlePublish() {
        setPublishing(true);
        try {
            const result = await gitPush();
            notify(result.pushed ? 'success' : 'info', result.message);
        } catch (err) {
            notify(
                'error',
                err instanceof Error ? err.message : 'Publish failed.'
            );
        } finally {
            setPublishing(false);
        }
    }

    function handleAdded(payload: Payload) {
        notify('success', `Added ${payload.name} (${payload.version ?? '?'}).`);
        void refresh();
    }

    function handleUpdated(item: Payload, message: string, changed: boolean) {
        setPayloads((prev) =>
            prev.map((p) => (p.name === item.name ? item : p))
        );
        notify(changed ? 'success' : 'info', message);
    }

    function handleRemoved(name: string) {
        setPayloads((prev) => prev.filter((p) => p.name !== name));
        notify('success', `Removed ${name}.`);
    }

    async function handleUpdateAll() {
        setUpdatingAll(true);
        try {
            const results = await updateAll();
            const changed = results.filter((r) => r.updated).length;
            setPayloads(await listPayloads());
            notify(
                changed > 0 ? 'success' : 'info',
                changed > 0
                    ? `Updated ${changed} of ${results.length} mirrors.`
                    : `All ${results.length} mirrors already up to date.`
            );
        } catch (err) {
            notify(
                'error',
                err instanceof Error ? err.message : 'Update-all failed.'
            );
        } finally {
            setUpdatingAll(false);
        }
    }

    return (
        <div className="mx-auto max-w-5xl px-5 py-10 md:py-14">
            <header className="animate-rise flex flex-wrap items-center justify-between gap-5">
                <div className="flex items-center gap-3.5">
                    <Logo />
                    <div>
                        {editingTitle ? (
                            <div className="flex items-center gap-2">
                                <input
                                    aria-label="Collection title"
                                    className="input h-10 max-w-xs font-display text-2xl font-bold"
                                    value={titleDraft}
                                    autoFocus
                                    maxLength={120}
                                    disabled={savingTitle}
                                    onChange={(e) => setTitleDraft(e.target.value)}
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter') void saveTitle();
                                        if (e.key === 'Escape') setEditingTitle(false);
                                    }}
                                />
                                <button
                                    type="button"
                                    className="btn btn-ghost h-10 w-10 !px-0"
                                    onClick={() => void saveTitle()}
                                    disabled={savingTitle}
                                    aria-label="Save title">
                                    <IconCheck className="h-4 w-4 text-brand-600 dark:text-brand-300" />
                                </button>
                                <button
                                    type="button"
                                    className="btn btn-ghost h-10 w-10 !px-0"
                                    onClick={() => setEditingTitle(false)}
                                    disabled={savingTitle}
                                    aria-label="Cancel">
                                    <IconX className="h-4 w-4" />
                                </button>
                            </div>
                        ) : (
                            <div className="group flex items-center gap-2">
                                <h1 className="font-display text-3xl font-bold leading-none tracking-tight text-ink">
                                    {title || 'Payloads Mirror'}
                                </h1>
                                <button
                                    type="button"
                                    className="rounded-lg p-1.5 text-faint opacity-0 transition hover:bg-paper hover:text-ink focus-visible:opacity-100 group-hover:opacity-100"
                                    onClick={() => {
                                        setTitleDraft(title);
                                        setEditingTitle(true);
                                    }}
                                    aria-label="Edit collection title"
                                    title="Edit title">
                                    <IconPencil className="h-4 w-4" />
                                </button>
                            </div>
                        )}
                        <p className="mt-1.5 text-[0.95rem] text-muted">
                            {loading
                                ? 'Loading…'
                                : `${payloads.length} PS5 payloads mirrored & kept fresh`}
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-2.5">
                    <a
                        href="/payloads.json"
                        target="_blank"
                        rel="noreferrer noopener"
                        className="btn btn-ghost btn-md font-mono"
                        title="Open the public payloads.json feed">
                        payloads.json
                        <IconExternal className="h-4 w-4" />
                    </a>
                    {gitEnabled && (
                        <button
                            type="button"
                            className="btn btn-ghost btn-md"
                            onClick={handlePublish}
                            disabled={anyBusy || loading}
                            title="Commit & push payloads.json + README.md to GitHub">
                            <IconUpload
                                className={`h-4 w-4 ${publishing ? 'animate-pulse' : ''}`}
                            />
                            {publishing ? 'Publishing…' : 'Publish'}
                        </button>
                    )}
                    <button
                        type="button"
                        className="btn btn-ghost h-11 w-11 !px-0"
                        onClick={toggleTheme}
                        aria-label={
                            theme === 'dark'
                                ? 'Switch to light mode'
                                : 'Switch to dark mode'
                        }
                        title={theme === 'dark' ? 'Light mode' : 'Dark mode'}>
                        {theme === 'dark' ? (
                            <IconSun className="h-[1.15rem] w-[1.15rem]" />
                        ) : (
                            <IconMoon className="h-[1.15rem] w-[1.15rem]" />
                        )}
                    </button>
                    <button
                        type="button"
                        className="btn btn-md btn-primary"
                        onClick={handleUpdateAll}
                        disabled={anyBusy || loading}>
                        <IconSync
                            className={`h-4 w-4 ${updatingAll ? 'animate-spin' : ''}`}
                        />
                        {updatingAll ? 'Updating…' : 'Update all'}
                    </button>
                </div>
            </header>

            <main className="mt-9 flex flex-col gap-6">
                <div className="grid gap-6 md:grid-cols-2">
                    <div
                        className="animate-rise"
                        style={{ animationDelay: '0.06s' }}>
                        <AddMirrorForm
                            onAdded={handleAdded}
                            onError={(m) => notify('error', m)}
                        />
                    </div>
                    <div
                        className="animate-rise"
                        style={{ animationDelay: '0.12s' }}>
                        <SchedulerPanel
                            onError={(m) => notify('error', m)}
                            onRunComplete={(summary) => {
                                notify('info', `Scheduled update: ${summary}`);
                                void refresh();
                            }}
                        />
                    </div>
                </div>

                <section
                    className="animate-rise"
                    style={{ animationDelay: '0.18s' }}
                    aria-busy={loading}>
                    <div className="mb-3 flex items-center justify-between gap-3 px-1">
                        <h2 className="font-display text-xl font-semibold text-ink">
                            Mirrors
                        </h2>
                        <div className="flex items-center gap-3">
                            {!loading && (
                                <span className="text-sm text-faint">
                                    {payloads.length} total
                                </span>
                            )}
                        </div>
                    </div>
                    {loading ? (
                        <div className="card grid place-items-center px-6 py-16 text-muted">
                            Loading mirrors…
                        </div>
                    ) : (
                        <PayloadTable
                            payloads={payloads}
                            busyName={busyName}
                            onSetBusy={setBusyName}
                            onUpdated={handleUpdated}
                            onRemoved={handleRemoved}
                            onError={(m) => notify('error', m)}
                        />
                    )}
                </section>
            </main>

            <Toast toast={toast} onDismiss={() => setToast(null)} />
        </div>
    );
}
