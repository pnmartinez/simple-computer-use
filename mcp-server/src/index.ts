#!/usr/bin/env node

/**
 * LLM Control MCP Server
 * 
 * This MCP server allows Cursor to push updates to the LLM Control Flask server,
 * which then delivers them to connected clients (e.g., Android app) via long polling.
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ErrorCode,
  McpError,
} from "@modelcontextprotocol/sdk/types.js";

// Configuration from environment variables
const LLM_CONTROL_HOST = process.env.LLM_CONTROL_HOST || "http://localhost:5000";

/**
 * Push an update to the LLM Control server
 */
async function pushUpdate(
  summary: string,
  changes?: string[],
  type?: string,
  metadata?: Record<string, unknown>
): Promise<{ success: boolean; id?: string; error?: string }> {
  const url = `${LLM_CONTROL_HOST}/push-update`;
  
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        summary,
        changes: changes || [],
        type: type || "cursor_update",
        metadata: metadata || {},
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      return {
        success: false,
        error: `Server error ${response.status}: ${errorText}`,
      };
    }

    const result = await response.json();
    return {
      success: true,
      id: result.id,
    };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Unknown error",
    };
  }
}

/**
 * Check if the LLM Control server is running
 */
async function checkServerHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${LLM_CONTROL_HOST}/health`, {
      method: "GET",
      signal: AbortSignal.timeout(5000),
    });
    return response.ok;
  } catch {
    return false;
  }
}

// Create the MCP server
const server = new Server(
  {
    name: "llm-control-mcp",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// List available tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "push_update",
        description: `Send an update/summary to the LLM Control server. This update will be delivered to connected clients (e.g., Android app) via long polling. Use this to notify users about completed tasks, code changes, or any important information.

Server: ${LLM_CONTROL_HOST}`,
        inputSchema: {
          type: "object",
          properties: {
            summary: {
              type: "string",
              description: "A human-readable summary of the changes or update. This will be displayed to the user. Be concise but informative.",
            },
            changes: {
              type: "array",
              items: { type: "string" },
              description: "Optional list of files or items that were changed. E.g., ['login.py', 'auth/validators.py']",
            },
            type: {
              type: "string",
              description: "Type of update. Defaults to 'cursor_update'. Other options: 'task_complete', 'error', 'info'",
              default: "cursor_update",
            },
          },
          required: ["summary"],
        },
      },
      {
        name: "check_server_status",
        description: `Check if the LLM Control server is running and accessible at ${LLM_CONTROL_HOST}`,
        inputSchema: {
          type: "object",
          properties: {},
          required: [],
        },
      },
    ],
  };
});

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  switch (name) {
    case "push_update": {
      const { summary, changes, type } = args as {
        summary: string;
        changes?: string[];
        type?: string;
      };

      if (!summary || typeof summary !== "string") {
        throw new McpError(
          ErrorCode.InvalidParams,
          "Missing required parameter: summary"
        );
      }

      const result = await pushUpdate(summary, changes, type);

      if (result.success) {
        return {
          content: [
            {
              type: "text",
              text: `✅ Update pushed successfully!\nID: ${result.id}\nSummary: "${summary}"`,
            },
          ],
        };
      } else {
        return {
          content: [
            {
              type: "text",
              text: `❌ Failed to push update: ${result.error}`,
            },
          ],
          isError: true,
        };
      }
    }

    case "check_server_status": {
      const isHealthy = await checkServerHealth();

      return {
        content: [
          {
            type: "text",
            text: isHealthy
              ? `✅ LLM Control server is running at ${LLM_CONTROL_HOST}`
              : `❌ LLM Control server is not accessible at ${LLM_CONTROL_HOST}`,
          },
        ],
      };
    }

    default:
      throw new McpError(ErrorCode.MethodNotFound, `Unknown tool: ${name}`);
  }
});

// Start the server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error(`LLM Control MCP server running (target: ${LLM_CONTROL_HOST})`);
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
