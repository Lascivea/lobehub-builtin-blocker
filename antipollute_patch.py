#!/usr/bin/env python3
"""Patch minified Next.js chunks to disable polluted builtin tools/skills.

Seven patch points, all env-driven by DISABLED_BUILTIN_TOOLS (comma-separated):
  P1: Activator getToolManifests    - skip blacklisted tool ids
  P2: toolManifestMap construction  - skip blacklisted tool ids at build time
  P3: SkillEngine enableChecker     - block blacklisted skill identifiers
  P4: injectSelfFeedbackIntentTool  - block direct injection of lobe-self-iteration
  P5: TaskIdentifier forced plugin  - block lobe-task from being forced into plugins
  P6: post-filter after generateToolsDetailed - remove blacklisted from tools+enabledToolIds
  P7: builtinTools registry - remove blacklisted tools from discovery candidates

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

# P2: toolManifestMap construction — primary defense for tools (variable renamed tC->t_)
P2_OLD = '!1===e.discoverable||t_[e.identifier]||(t_[e.identifier]=e.manifest)'
P2_NEW = '!1===e.discoverable||(process.env.DISABLED_BUILTIN_TOOLS||"").split(",").map(s=>s.trim()).includes(e.identifier)||t_[e.identifier]||(t_[e.identifier]=e.manifest)'

# P3: SkillEngine enableChecker — defense for skills (lobehub, task, etc.)
P3_OLD = (
    'z=new I.SkillEngine({enableChecker:e=>'
    '(0,X.shouldEnableBuiltinSkill)(e.identifier,{canExecuteOnDevice:!!Q&&(0,K.isDeviceCapablePlan)(Q)}),skills:c}).generate(tj??[])'
)
P3_NEW = (
    'z=new I.SkillEngine({enableChecker:e=>'
    '(process.env.DISABLED_BUILTIN_TOOLS||"").split(",").map(s=>s.trim()).includes(e.identifier)'
    '?false:(0,X.shouldEnableBuiltinSkill)(e.identifier,{canExecuteOnDevice:!!Q&&(0,K.isDeviceCapablePlan)(Q)}),skills:c}).generate(tj??[])'
)

# P4: injectSelfFeedbackIntentTool — block direct injection of lobe-self-iteration
P4_OLD = (
    '(0,A.shouldExposeSelfFeedbackIntentTool)({agentSelfIterationEnabled:a,'
    'disableSelfFeedbackIntentTool:t.disableSelfFeedbackIntentTool,featureUserEnabled:e})'
    '&&(B=B??[],(0,A.injectSelfFeedbackIntentTool)({enabledToolIds:tR.enabledToolIds,'
    'manifestMap:t_,sourceMap:tD,tools:B}),ex("execAgent: injected self-feedback intent declaration tool"))'
)
P4_NEW = (
    '(0,A.shouldExposeSelfFeedbackIntentTool)({agentSelfIterationEnabled:a,'
    'disableSelfFeedbackIntentTool:t.disableSelfFeedbackIntentTool,featureUserEnabled:e})'
    '&&!((process.env.DISABLED_BUILTIN_TOOLS||"").split(",").map(s=>s.trim()).includes("lobe-self-iteration"))'
    '&&(B=B??[],(0,A.injectSelfFeedbackIntentTool)({enabledToolIds:tR.enabledToolIds,'
    'manifestMap:t_,sourceMap:tD,tools:B}),ex("execAgent: injected self-feedback intent declaration tool"))'
)

# P5: TaskIdentifier forced plugin injection — block lobe-task from being forced into plugins
P5_OLD = 'tn=tn.includes(f.TaskIdentifier)?tn:[f.TaskIdentifier,...tn]'
P5_NEW = 'tn=((process.env.DISABLED_BUILTIN_TOOLS||"").split(",").map(s=>s.trim()).includes("lobe-task"))?tn:tn.includes(f.TaskIdentifier)?tn:[f.TaskIdentifier,...tn]'

# P6: post-filter after generateToolsDetailed - remove blacklisted from tools+enabledToolIds+manifestMap
P6_OLD = 'ex("execAgent: enabled tool ids: %O",tR.enabledToolIds);let J=e=>!(i.has(e)||!th&&(0,eB.isDeviceToolIdentifier)(e)||L&&eB.REMOTE_DEVICE_TOOL_IDENTIFIERS.has(e)),X=$.getEnabledPluginManifests(V);'
P6_NEW = 'ex("execAgent: enabled tool ids: %O",tR.enabledToolIds);let _bl=(process.env.DISABLED_BUILTIN_TOOLS||"").split(",").map(s=>s.trim()).filter(Boolean);B=B.filter(e=>{let n=e?.function?.name||e?.name;return!n||!_bl.some(id=>n.includes(id))});tR.enabledToolIds=tR.enabledToolIds.filter(id=>!_bl.some(bl=>id.includes(bl)));_bl.forEach(b=>{delete t_[b]});let J=e=>!(i.has(e)||!th&&(0,eB.isDeviceToolIdentifier)(e)||L&&eB.REMOTE_DEVICE_TOOL_IDENTIFIERS.has(e)),X=$.getEnabledPluginManifests(V);'

# P7: builtinTools registry — remove blacklisted tools from discovery candidates
P7_OLD = '].map(e=>({...e,avatar:e.manifest?.meta?.avatar,description:e.manifest?.meta?.description,tags:e.manifest?.meta?.tags,title:e.manifest?.meta?.title})),eE='
P7_NEW = '].map(e=>({...e,avatar:e.manifest?.meta?.avatar,description:e.manifest?.meta?.description,tags:e.manifest?.meta?.tags,title:e.manifest?.meta?.title})).filter(e=>!((process.env.DISABLED_BUILTIN_TOOLS||"").split(",").map(s=>s.trim()).filter(Boolean).includes(e.identifier))),eE='

PATCHES = [
    ("P1", P1_OLD, P1_NEW),
    ("P2", P2_OLD, P2_NEW),
    ("P3", P3_OLD, P3_NEW),
    ("P4", P4_OLD, P4_NEW),
    ("P5", P5_OLD, P5_NEW),
    ("P6", P6_OLD, P6_NEW),
    ("P7", P7_OLD, P7_NEW),
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
    only = None
    for arg in sys.argv[1:]:
        if arg.startswith("--only="):
            only = {name.strip() for name in arg.split("=", 1)[1].split(",") if name.strip()}
    files = [f for f in sys.argv[1:] if f != "--apply" and not f.startswith("--only=")]
    any_skip = False
    for f in files:
        s = open(f).read()
        selected = [item for item in PATCHES if only is None or item[0] in only]
        original = PATCHES[:]
        PATCHES[:] = selected
        new, rep = patch(s)
        PATCHES[:] = original
        print(f"{f}:")
        print("\n".join(rep))
        if any(": SKIP" in r for r in rep):
            # 完全无关的文件(所有 patch 都 SKIP)不算失败
            if not all(": SKIP" in r for r in rep):
                any_skip = True
        if not dry and new != s:
            open(f, "w").write(new)
            print(f"  -> written")
        elif dry:
            print(f"  (dry-run)")
    if any_skip:
        print("\nERROR: some patches did not match (minified structure changed?)", file=sys.stderr)
        sys.exit(1)
