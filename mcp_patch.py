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

# P2: MCPClient.callTool - add catch
P2_OLD = 'async callTool(e,t){V("Calling tool: %s with args: %O, timeout: %O",e,t,B);let r=await this.mcp.callTool({arguments:t,name:e},void 0,{timeout:B});return V("Tool call result: %O",r),r}'
P2_NEW = ('async callTool(e,t){V("Calling tool: %s with args: %O, timeout: %O",e,t,B);'
          'try{let r=await this.mcp.callTool({arguments:t,name:e},void 0,{timeout:B});'
          'return V("Tool call result: %O",r),r}'
          'catch(e){if(e instanceof Error&&' + SESSION_RE + '.test(e.message))'
          'throw new Error("NoValidSessionId",{cause:e});throw e}}')

# P3: MCPClient.listResources - add NoValidSessionId throw in catch
P3_OLD = 'async listResources(){try{V("Listing resources...");let{resources:e}=await this.mcp.listResources();return V("Listed resources: %O",e),e}catch(e){return V("Listed resources: %O",e),[]}}'
P3_NEW = ('async listResources(){try{V("Listing resources...");let{resources:e}=await this.mcp.listResources();'
          'return V("Listed resources: %O",e),e}'
          'catch(e){if(e instanceof Error&&' + SESSION_RE + '.test(e.message))'
          'throw new Error("NoValidSessionId",{cause:e});return V("Listed resources: %O",e),[]}}')

# P4: MCPClient.listPrompts
P4_OLD = 'async listPrompts(){try{V("Listing prompts...");let{prompts:e}=await this.mcp.listPrompts();return V("Listed prompts: %O",e),e}catch(e){return V("Listed prompts: %O",e),[]}}'
P4_NEW = ('async listPrompts(){try{V("Listing prompts...");let{prompts:e}=await this.mcp.listPrompts();'
          'return V("Listed prompts: %O",e),e}'
          'catch(e){if(e instanceof Error&&' + SESSION_RE + '.test(e.message))'
          'throw new Error("NoValidSessionId",{cause:e});return V("Listed prompts: %O",e),[]}}')

# P5: MCPService.callTool - wrap with one-shot retry on NoValidSessionId
P5_OLD = (
    'async callTool(e){let{clientParams:t,toolName:i,argsStr:s,processContentBlocks:a}=e,'
    'l=await this.getClient(t),c=(0,r.safeParseJSON)(s),u=this.sanitizeForLogging(t);'
    'en(`Calling tool "${i}" using client for params: %O with args: %O`,u,c);'
    'try{let e=await l.callTool(i,c),t=await ei.processToolCallResult(e,a);'
    'return en(`Tool "${i}" called successfully for params: %O, result: %O`,u,t.state),t}'
    'catch(e){if(e instanceof o.McpError)return{content:e.message,error:e,'
    'state:{content:[{text:e.message,type:"text"}],isError:!0},success:!1};'
    'throw console.error(`Error calling tool "${i}" for params %O:`,this.sanitizeForLogging(t),e),'
    'new n.TRPCError({cause:e,code:"INTERNAL_SERVER_ERROR",'
    'message:`Error calling tool "${i}" on MCP server: ${e.message}`})}}'
)
P5_NEW = (
    'async callTool(e){let _run=async()=>{'
    'let{clientParams:t,toolName:i,argsStr:s,processContentBlocks:a}=e,'
    'l=await this.getClient(t),c=(0,r.safeParseJSON)(s),u=this.sanitizeForLogging(t);'
    'en(`Calling tool "${i}" using client for params: %O with args: %O`,u,c);'
    'try{let e=await l.callTool(i,c),t=await ei.processToolCallResult(e,a);'
    'return en(`Tool "${i}" called successfully for params: %O, result: %O`,u,t.state),t}'
    'catch(e){if("NoValidSessionId"===e.message)throw e;'
    'if(e instanceof o.McpError)return{content:e.message,error:e,'
    'state:{content:[{text:e.message,type:"text"}],isError:!0},success:!1};'
    'throw console.error(`Error calling tool "${i}" for params %O:`,this.sanitizeForLogging(t),e),'
    'new n.TRPCError({cause:e,code:"INTERNAL_SERVER_ERROR",'
    'message:`Error calling tool "${i}" on MCP server: ${e.message}`})}};'
    'try{return await _run()}'
    'catch(err){if("NoValidSessionId"===err.message){'
    'let k=this.serializeParams(e.clientParams);this.clients.delete(k);'
    'en(`Session expired for tool call, reinitializing client`);'
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
        if any(r.endswith(": SKIP") for r in rep):
            any_skip = True
        if not dry and new != s:
            open(f, "w").write(new)
            print(f"  -> written")
        elif dry:
            print(f"  (dry-run, not written)")
    if any_skip:
        print("\nERROR: some patches did not match (minified structure changed?)", file=sys.stderr)
        sys.exit(1)
