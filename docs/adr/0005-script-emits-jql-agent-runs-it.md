# The script emits JQL and the agent runs it

The forecaster's script never calls Jira and never holds a credential. It prints the JQL operations it needs, the agent runs them through the Atlassian MCP, and the raw results go back into the script. This is the pattern `ticketer` already uses.

The cost is a round trip for each query, including one changelog read per ticket to find when it first reached Testing or Done. The benefit is that the script stays stdlib-only and testable offline from saved results, and the skill behaves the same on any agent that has an Atlassian tool.
