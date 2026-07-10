#!/usr/bin/env python3
"""Patch minified Next.js chunks to disable polluted builtin tools/skills.

Six patch points, all env-driven by DISABLED_BUILTIN_TOOLS (comma-separated):
  P1: Activator getToolManifests    - skip blacklisted tool ids
  P2: toolManifestMap construction  - skip blacklisted tool ids at build time
  P3: SkillEngine enableChecker     - block blacklisted skill identifiers
  P4: injectSelfFeedbackIntentTool  - block direct injection of lobe-self-iteration
  P5: TaskIdentifier forced plugin  - block lobe-task from being forced into plugins
  P6: post-filter after generateToolsDetailed - remove blacklisted from tools+enabledToolIds

Empty / undefined DISABLED_BUILTIN_TOOLS = no filtering (official behavior).
"""
import sys

# P1: Activator runtime getToolManifests
P1_OLD = (
    'getToolManifests:async t=>{let a=[];for(let i of t){'
    'let t=e.toolManifestMap[i];t&&a.push({apiDescriptions:t.api.map(e=>({description:e.description,name:e.name})),'
    'identifier:t.identifier,name:t.meta?.title??t.identifier,systemRole:t.systemRole})}'
)
P1_NEW = (
    'getToolManifests:async t=>{let a=[],_bl=(process.env.DISABLED_BUILTIN_TOOLS||"").split(",").map(s=>s.trim()).filter(Boolean);'
    'for(let i of t){if(_bl.includes(i))continue;'
    'let t=e.toolManifestMap[i];t&&a.push({apiDescriptions:t.api.map(e=>({description:e.description,name:e.name})),'
    'identifier:t.identifier,name:t.meta?.title??t.identifier,systemRole:t.systemRole})}'
)

# P2: toolManifestMap construction — primary defense for tools
P2_OLD = '!1===e.discoverable||tC[e.identifier]||(tC[e.identifier]=e.manifest)'
P2_NEW = '!1===e.discoverable||(process.env.DISABLED_BUILTIN_TOOLS||"").split(",").map(s=>s.trim()).includes(e.identifier)||tC[e.identifier]||(tC[e.identifier]=e.manifest)'

# P3: SkillEngine enableChecker — defense for skills (lobehub, task, etc.)
P3_OLD = (
    'new y.SkillEngine({enableChecker:e=>'
    '(0,$.shouldEnableBuiltinSkill)(e.identifier,{canExecuteOnDevice:!!O&&(0,H.isDeviceCapablePlan)(O)}),skills:c})'
)
P3_NEW = (
    'new y.SkillEngine({enableChecker:e=>'
    '(process.env.DISABLED_BUILTIN_TOOLS||"").split(",").map(s=>s.trim()).includes(e.identifier)'
    '?false:(0,$.shouldEnableBuiltinSkill)(e.identifier,{canExecuteOnDevice:!!O&&(0,H.isDeviceCapablePlan)(O)}),skills:c})'
)

# P4: injectSelfFeedbackIntentTool — block direct injection of lobe-self-iteration
P4_OLD = (
    '(0,h.shouldExposeSelfFeedbackIntentTool)({agentSelfIterationEnabled:a,'
    'disableSelfFeedbackIntentTool:t.disableSelfFeedbackIntentTool,featureUserEnabled:e})'
    '&&(M=M??[],(0,h.injectSelfFeedbackIntentTool)({enabledToolIds:tE.enabledToolIds,'
    'manifestMap:tC,sourceMap:tS,tools:M})'
)
P4_NEW = (
    '(0,h.shouldExposeSelfFeedbackIntentTool)({agentSelfIterationEnabled:a,'
    'disableSelfFeedbackIntentTool:t.disableSelfFeedbackIntentTool,featureUserEnabled:e})'
    '&&!((process.env.DISABLED_BUILTIN_TOOLS||"").split(",").map(s=>s.trim()).includes("lobe-self-iteration"))'
    '&&(M=M??[],(0,h.injectSelfFeedbackIntentTool)({enabledToolIds:tE.enabledToolIds,'
    'manifestMap:tC,sourceMap:tS,tools:M})'
)

# P5: TaskIdentifier forced plugin injection — block lobe-task from being forced into plugins
P5_OLD = 'e9.plugins=e9.plugins?.includes(m.TaskIdentifier)?e9.plugins:[m.TaskIdentifier,...e9.plugins??[]]'
P5_NEW = 'e9.plugins=((process.env.DISABLED_BUILTIN_TOOLS||"").split(",").map(s=>s.trim()).includes("lobe-task"))?e9.plugins:e9.plugins?.includes(m.TaskIdentifier)?e9.plugins:[m.TaskIdentifier,...e9.plugins??[]]'

# P6: post-filter after generateToolsDetailed - remove blacklisted from tools+enabledToolIds+manifestMap
P6_OLD = 'eM("execAgent: enabled tool ids: %O",tE.enabledToolIds);let z=e=>'
P6_NEW = 'eM("execAgent: enabled tool ids: %O",tE.enabledToolIds);let _bl=(process.env.DISABLED_BUILTIN_TOOLS||"").split(",").map(s=>s.trim()).filter(Boolean);tE.tools=tE.tools.filter(e=>{let n=e?.function?.name||e?.name;return!n||!_bl.some(id=>n.includes(id))});tE.enabledToolIds=tE.enabledToolIds.filter(id=>!_bl.some(bl=>id.includes(bl)));_bl.forEach(b=>{delete tC[b]});let z=e=>'

PATCHES = [
    ("P1", P1_OLD, P1_NEW),
    ("P2", P2_OLD, P2_NEW),
    ("P3", P3_OLD, P3_NEW),
    ("P4", P4_OLD, P4_NEW),
    ("P5", P5_OLD, P5_NEW),
    ("P6", P6_OLD, P6_NEW),
]


def patch(text):
    report = []
    for name, old, new in PATCHES:
        cnt = text.count(old)
        if cnt != 1:
            report.append(f"  {name}: SKIP (found {cnt} matches, expected 1)")
            continue
        text = text.replace(old, new, 1)
        report.append(f"  {name}: OK")
    return text, report


if __name__ == "__main__":
    dry = "--apply" not in sys.argv
    files = [f for f in sys.argv[1:] if f != "--apply"]
    any_skip = False
    for f in files:
        s = open(f).read()
        new, rep = patch(s)
        print(f"{f}:")
        print("\n".join(rep))
        if any(r.endswith(": SKIP") for r in rep):
            any_skip = True
        if not dry and new != s:
            open(f, "w").write(new)
            print(f"  -> written")
        elif dry:
            print(f"  (dry-run)")
    if any_skip:
        print("\nERROR: some patches did not match (minified structure changed?)", file=sys.stderr)
        sys.exit(1)
