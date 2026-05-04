"""
RePORT India Clinical Data Query Example - Consultant-style Agent Pattern
=========================================================================

This example demonstrates how to use the ReAct RAG Agent to query
RePORT India (Regional Prospective Observational Research for Tuberculosis)
clinical study metadata using the consultant-style interaction pattern.

The agent acts as a TB epidemiology consultant who:
1. First answers conceptually based on domain knowledge
2. Only searches for specific variables when explicitly needed
3. Provides analysis recommendations without premature data dives

Study: RePORT India (Indo-VAP cohort)
Regulatory Framework: DPDPA 2023, ICMR Guidelines

Prerequisites:
    - OpenAI API key set in environment (OPENAI_API_KEY)
    - Data dictionary files in results/data_dictionary_mappings/
    - Metadata files in results/

Usage:
    python -m client.examples.query_clinical_data
    
    # Or with custom config:
    OPENAI_API_KEY=your-key python -m client.examples.query_clinical_data
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from reportalin.client.react_rag_agent import ReActConfig, ReActRAGAgent


async def run_consultant_queries():
    """
    Demonstrate consultant-style clinical data queries.
    
    The agent provides expert guidance on:
    - Study design and feasibility
    - Variable selection for research questions
    - Analysis recommendations
    """
    
    # Check for API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  OPENAI_API_KEY not set. Running in demo mode (tools only).")
        print("   Set OPENAI_API_KEY to enable full agent responses.\n")
        api_key = "demo-key"
    
    print("=" * 70)
    print("RePORT India Clinical Data Consultation")
    print("=" * 70)
    print()
    
    # Configure the ReAct RAG Agent
    config = ReActConfig(
        llm_provider="openai",
        llm_api_key=api_key,
        llm_model="gpt-4o-mini",  # Cost-effective for consultations
        temperature=0.3,  # Low temperature for factual responses
        max_iterations=5,
        use_mcp_tools=False,  # Use local RAG tools only
    )
    
    agent = ReActRAGAgent(config)
    
    # Connect the agent (initializes local tools)
    await agent.connect()
    
    try:
        # =====================================================================
        # Example 1: Conceptual Question (No Tool Needed)
        # =====================================================================
        print("\n" + "=" * 70)
        print("Query 1: Conceptual Analysis Question")
        print("=" * 70)
        print()
        
        query1 = """
        I'm interested in studying TB recurrence risk factors. 
        What would be a good analytical approach for this research question?
        """
        print(f"Question: {query1.strip()}")
        print("-" * 40)
        
        if api_key != "demo-key":
            response = await agent.run(query1)
            print(f"\nAgent Response:\n{response}")
        else:
            # Demo mode - just show what tools would be available
            print("\n[Demo mode - showing available tools]")
            tools = agent._get_all_tools()
            for tool in tools:
                print(f"  - {tool['function']['name']}: {tool['function']['description'][:60]}...")
        
        # =====================================================================
        # Example 2: Variable Lookup (Tool Required)
        # =====================================================================
        print("\n" + "=" * 70)
        print("Query 2: Specific Variable Lookup")
        print("=" * 70)
        print()
        
        query2 = """
        What specific variable names should I use to measure diabetes status 
        in the RePORT India dataset?
        """
        print(f"Question: {query2.strip()}")
        print("-" * 40)
        
        if api_key != "demo-key":
            response = await agent.run(query2)
            print(f"\nAgent Response:\n{response}")
        else:
            # Demo mode - execute tool directly
            print("\n[Demo mode - executing search_variables tool]")
            tool_call = {
                "function": {
                    "name": "search_variables",
                    "arguments": '{"query": "diabetes"}'
                }
            }
            result = await agent._execute_tool(tool_call)
            print(f"Tool Result: {result['result'][:500]}...")
        
        # =====================================================================
        # Example 3: Outcome Variables by Cohort
        # =====================================================================
        print("\n" + "=" * 70)
        print("Query 3: Outcome Variables for Cohort A")
        print("=" * 70)
        print()
        
        query3 = """
        What are the outcome variables available for measuring TB recurrence
        in Cohort A (TB index cases)?
        """
        print(f"Question: {query3.strip()}")
        print("-" * 40)
        
        if api_key != "demo-key":
            response = await agent.run(query3)
            print(f"\nAgent Response:\n{response}")
        else:
            # Demo mode - execute tool directly
            print("\n[Demo mode - executing find_outcome_variables tool]")
            tool_call = {
                "function": {
                    "name": "find_outcome_variables",
                    "arguments": '{"outcome_type": "recurrence", "cohort": "A"}'
                }
            }
            result = await agent._execute_tool(tool_call)
            print(f"Tool Result: {result['result']}")
        
        # =====================================================================
        # Example 4: Study Overview
        # =====================================================================
        print("\n" + "=" * 70)
        print("Query 4: Study Design Overview")
        print("=" * 70)
        print()
        
        query4 = "Give me an overview of the RePORT India study design."
        print(f"Question: {query4}")
        print("-" * 40)
        
        if api_key != "demo-key":
            response = await agent.run(query4)
            print(f"\nAgent Response:\n{response}")
        else:
            # Demo mode - execute tool directly
            print("\n[Demo mode - executing get_study_overview tool]")
            tool_call = {
                "function": {
                    "name": "get_study_overview",
                    "arguments": '{}'
                }
            }
            result = await agent._execute_tool(tool_call)
            print(f"Tool Result: {result['result'][:800]}...")
        
        # =====================================================================
        # Example 5: Visualization Recommendations
        # =====================================================================
        print("\n" + "=" * 70)
        print("Query 5: Visualization Recommendations")
        print("=" * 70)
        print()
        
        query5 = """
        What visualizations would you recommend for analyzing the relationship
        between diabetes and TB treatment outcomes, stratified by age and sex?
        """
        print(f"Question: {query5.strip()}")
        print("-" * 40)
        
        if api_key != "demo-key":
            response = await agent.run(query5)
            print(f"\nAgent Response:\n{response}")
        else:
            # Demo mode - execute tool directly
            print("\n[Demo mode - executing recommend_visualization tool]")
            tool_call = {
                "function": {
                    "name": "recommend_visualization",
                    "arguments": '{"outcome": "treatment_outcome", "predictors": ["diabetes"], "stratify_by": ["age", "sex"]}'
                }
            }
            result = await agent._execute_tool(tool_call)
            print(f"Tool Result: {result['result']}")
        
        print("\n" + "=" * 70)
        print("Consultation Complete")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n⚠️ Error: {e}")


async def run_interactive_session():
    """
    Run an interactive consultation session.
    
    Users can ask questions in natural language and receive
    expert-level guidance on TB clinical research.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  OPENAI_API_KEY required for interactive mode.")
        print("   Set: export OPENAI_API_KEY=your-key")
        return
    
    print("=" * 70)
    print("RePORT India Interactive Consultation")
    print("=" * 70)
    print()
    print("Ask questions about:")
    print("  - TB study design and feasibility")
    print("  - Variable selection for research")
    print("  - Analysis recommendations")
    print()
    print("Type 'quit' or 'exit' to end the session.")
    print()
    
    config = ReActConfig(
        llm_provider="openai",
        llm_api_key=api_key,
        llm_model="gpt-4o-mini",
        temperature=0.3,
        max_iterations=5,
        use_mcp_tools=False,
    )
    
    agent = ReActRAGAgent(config)
    await agent.connect()
    
    try:
        while True:
            print("-" * 40)
            query = input("You: ").strip()
            
            if not query:
                continue
            
            if query.lower() in ("quit", "exit", "q"):
                print("\nThank you for the consultation. Goodbye!")
                break
            
            try:
                response = await agent.run(query)
                print(f"\nConsultant: {response}\n")
            except Exception as e:
                print(f"\n⚠️  Error: {e}\n")
    
    except Exception as e:
        print(f"\n⚠️ Error: {e}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="RePORT India Clinical Data Consultation Examples"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run interactive consultation session"
    )
    
    args = parser.parse_args()
    
    if args.interactive:
        asyncio.run(run_interactive_session())
    else:
        asyncio.run(run_consultant_queries())


if __name__ == "__main__":
    main()
