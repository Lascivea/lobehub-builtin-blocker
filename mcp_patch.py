#!/usr/bin/env python3
"""Patch minified Next.js chunks to fix MCP session reuse bug.

Patches:
  P1: MCPClient.listTools  - broaden session-expiry error matching
  P2: MCPClient.callTool   - throw NoValidSessionId on session expiry
  P3: MCPClient.listResources - throw NoValidSessionId on session expiry
  P4: MCPClient.listPrompts   - throw NoValidSessionId on session expiry
  P5: MCPService.callTool  - retry once with fresh client on NoValidSessionId
"""
import sys, re

SESSION_RE = r"/no valid session id provided|session.*not found|session rebuild is disabled/i"

# P1: broaden listTools session detection
P1_OLD = 'e.message.includes("No valid session ID provided")'
P1_NEW = f'{SESSION_RE}.test(e.message)'

# P2: MCPClient.callTool - add catch (logger renamed V->J in recent canary)
P2_OLD = 'async callTool(e,t){J("Calling tool: %s with args: %O, timeout: %O",e,t,B);let r=await this.mcp.callTool({arguments:t,name:e},void 0,{timeout:B});return J("Tool call result: %O",r),r}'
P2_NEW = ('async callTool(e,t){J("Calling tool: %s with args: %O, timeout: %O",e,t,B);'
          'try{let r=await this.mcp.callTool({arguments:t,name:e},void 0,{timeout:B});'
          'return J("Tool call result: %O",r),r}'
          'catch(e){if(e instanceof Error&&' + SESSION_RE + '.test(e.message))'
          'throw new Error("NoValidSessionId",{cause:e});throw e}}')

# P3: MCPClient.listResources - add NoValidSessionId throw in catch
P3_OLD = 'async listResources(){try{J("Listing resources...");let{resources:e}=await this.mcp.listResources();return J("Listed resources: %O",e),e}catch(e){return J("Listed resources: %O",e),[]}}'
P3_NEW = ('async listResources(){try{J("Listing resources...");let{resources:e}=await this.mcp.listResources();'
          'return J("Listed resources: %O",e),e}'
          'catch(e){if(e instanceof Error&&' + SESSION_RE + '.test(e.message))'
          'throw new Error("NoValidSessionId",{cause:e});return J("Listed resources: %O",e),[]}}')

# P4: MCPClient.listPrompts
P4_OLD = 'async listPrompts(){try{J("Listing prompts...");let{prompts:e}=await this.mcp.listPrompts();return J("Listed prompts: %O",e),e}catch(e){return J("Listed prompts: %O",e),[]}}'
P4_NEW = ('async listPrompts(){try{J("Listing prompts...");let{prompts:e}=await this.mcp.listPrompts();'
          'return J("Listed prompts: %O",e),e}'
          'catch(e){if(e instanceof Error&&' + SESSION_RE + '.test(e.message))'
          'throw new Error("NoValidSessionId",{cause:e});return J("Listed prompts: %O",e),[]}}')

# P5: MCPService.callTool - wrap with one-shot retry on NoValidSessionId
# Updated for canary where McpError is "s.McpError" and TRPCError is "o.TRPCError"
P5_OLD = (
    'async callTool(e){let{clientParams:t,toolName:a,argsStr:i,processContentBlocks:n}=e,'
    'l=await this.getClient(t),c=(0,r.safeParseJSON)(i),d=this.sanitizeForLogging(t);'
    'ea(`Calling tool "${a}" using client for params: %O with args: %O`,d,c);'
    'try{let e=await l.callTool(a,c),t=await ei.processToolCallResult(e,n);'
    'return ea(`Tool "${a}" called successfully for params: %O, result: %O`,d,t.state),t}'
    'catch(e){if(e instanceof s.McpError)return{content:e.message,error:e,'
    'state:{content:[{text:e.message,type:"text"}],isError:!0},success:!1};'
    'throw console.error(`Error calling tool "${a}" for params %O:`,this.sanitizeForLogging(t),e),'
    'new o.TRPCError({cause:e,code:"INTERNAL_SERVER_ERROR",'
    'message:`Error calling tool "${a}" on MCP server: ${e.message}`})}}'
)
P5_NEW = (
    'async callTool(e){let _run=async()=>{'
    'let{clientParams:t,toolName:a,argsStr:i,processContentBlocks:n}=e,'
    'l=await this.getClient(t),c=(0,r.safeParseJSON)(i),d=this.sanitizeForLogging(t);'
    'ea(`Calling tool "${a}" using client for params: %O with args: %O`,d,c);'
    'try{let e=await l.callTool(a,c),t=await ei.processToolCallResult(e,n);'
    'return ea(`Tool "${a}" called successfully for params: %O, result: %O`,d,t.state),t}'
    'catch(e){if("NoValidSessionId"===e.message)throw e;'
    'if(e instanceof s.McpError)return{content:e.message,error:e,'
    'state:{content:[{text:e.message,type:"text"}],isError:!0},success:!1};'
    'throw console.error(`Error calling tool "${a}" for params %O:`,this.sanitizeForLogging(t),e),'
    'new o.TRPCError({cause:e,code:"INTERNAL_SERVER_ERROR",'
    'message:`Error calling tool "${a}" on MCP server: ${e.message}`})}};'
    'try{return await _run()}'
    'catch(err){if("NoValidSessionId"===err.message){'
    'let k=this.serializeParams(e.clientParams);this.clients.delete(k);'
    'ea(`Session expired for tool call, reinitializing client`);'
    'return await _run()}throw err}}'
)

PATCHES = [("P1", P1_OLD, P1_NEW), ("P2", P2_OLD, P2_NEW), ("P3", P3_OLD, P3_NEW),
           ("P4", P4_OLD, P4_NEW), ("P5", P5_OLD, P5_NEW)]

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
    files = sys.argv[1:]
    files = [f for f in files if f != "--apply"]
    any_skip = False
    for f in files:
        s = open(f).read()
        new, rep = patch(s)
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
            print(f"  (dry-run, not written)")
    if any_skip:
        print("\nERROR: some patches did not match (minified structure changed?)", file=sys.stderr)
        sys.exit(1)
