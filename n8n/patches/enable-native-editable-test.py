#!/usr/bin/env python3
"""Enable actual native Vue-Flow editing in n8n's isolated preview canvas only.

n8n upstream v2.44.5 pins the /workflows/demo route to read-only. This patch
reuses *upstream* NodeView, Canvas, NodeCreation and NodeDetails components.
Changes are intentionally scoped to ?editable=true and N8N_PREVIEW_MODE=true.
Never change normal /workflow/* permission checks or backend auth routes.

Saved draft is sent via postMessage to our same-origin test portal, which
persists it in the browser and reloads it after refresh. No real orders and
no credentials. The portal clearly labels this as browser-local draft storage.
"""
from pathlib import Path

root = Path("/src/packages/frontend/editor-ui/src")
changes = []

def edit(relpath, replacements):
    path = root / relpath
    original = path.read_text(encoding="utf-8")
    text = original
    for marker, replacement in replacements:
        hits = text.count(marker)
        if hits != 1:
            raise RuntimeError(f"Expected one match in {relpath}; found {hits} for {marker[:110]!r}")
        text = text.replace(marker, replacement, 1)
    path.write_text(text, encoding="utf-8")
    changes.append(str(path) + f" ({len(replacements)} anchored changes)")
    if text == original:
        raise RuntimeError("No modification " + str(path))

edit("app/views/NodeView.vue", [
    (
        "const isDemoRoute = computed(() => route.name === VIEWS.DEMO);",
        """const isDemoRoute = computed(() => route.name === VIEWS.DEMO);
// Editable workflow test ONLY on our isolated upstream preview instance.
// Do not grant editing to authenticated production workflows or normal demo links.
const isNativeEditableTest = computed(
    () => settingsStore.isPreviewMode && isDemoRoute.value && route.query.editable === 'true',
);""",
    ),
    (
        """const isCanvasReadOnly = computed(() => {
	return (
		isDemoRoute.value ||""",
        """const isCanvasReadOnly = computed(() => {
    if (isNativeEditableTest.value) return false;
	return (
		isDemoRoute.value ||""",
    ),
    (
        """async function onSaveWorkflow() {
	await workflowSaving.saveCurrentWorkflow({});
}""",
        """async function onSaveWorkflow() {
    if (isNativeEditableTest.value) {
        if (window.parent && workflowDocumentStore.value) {
            window.parent.postMessage(
                JSON.stringify({
                    command: 'testWorkflowSnapshot',
                    workflow: workflowDocumentStore.value.serialize(),
                }),
                window.location.origin,
            );
        }
        return;
    }
	await workflowSaving.saveCurrentWorkflow({});
}""",
    ),
    (
        """function checkIfEditingIsAllowed(): boolean {
	if (!uiStore.nodeViewInitialized) {""",
        """function checkIfEditingIsAllowed(): boolean {
    // Allow native drag, add, delete, connect, rename and NDV editing for
    // the isolated browser-local test route only.
    if (isNativeEditableTest.value) return true;
	if (!uiStore.nodeViewInitialized) {""",
    ),
]);
edit("app/router.ts", [
    (
        "route.meta.readOnlyCanvas = !EDITABLE_CANVAS_VIEWS.includes((route?.name ?? '') as VIEWS);",
        """route.meta.readOnlyCanvas =
        route?.name !== VIEWS.DEMO &&
        !EDITABLE_CANVAS_VIEWS.includes((route?.name ?? '') as VIEWS);""",
    ),
]);
edit("app/composables/usePostMessageHandler.ts", [
    (
        """} else if (json?.command === 'resetWorkflow') {
				resetWorkspace();""",
        """} else if (json?.command === 'saveTestWorkflow') {
                // Same-origin portal requests current REAL n8n document snapshot.
                if (route.name === VIEWS.DEMO && route.query.editable === 'true') {
                    const doc = currentWorkflowDocumentStore.value;
                    if (doc && window.parent) {
                        window.parent.postMessage(
                            JSON.stringify({
                                command: 'testWorkflowSnapshot',
                                workflow: doc.serialize(),
                            }),
                            window.location.origin,
                        );
                    }
                }
            } else if (json?.command === 'resetWorkflow') {
				resetWorkspace();""",
    ),
]);
print("\n".join(changes))
print("NATIVE_N8N_EDIT_PATCH_OK")
