"""Main entry point for ingesting a source and processing its contents."""

import asyncio
import inspect
import os
import shutil
from typing import Optional, Set, Tuple, Union
from pathlib import Path

from gitingest.cloning import clone_repo
from gitingest.config import TMP_BASE_PATH
from gitingest.ingestion import ingest_query
from gitingest.query_parsing import IngestionQuery, parse_query


async def ingest_async(
    source: str,
    temp_clone_dir: str = None,
    max_file_size: int = 10 * 1024 * 1024,  # 10 MB
    include_patterns: Optional[Union[str, Set[str]]] = None,
    exclude_patterns: Optional[Union[str, Set[str]]] = None,
    branch: Optional[str] = None,
    token: Optional[str] = None,
    output: Optional[str] = None,
) -> Tuple[str, str, str]:
    """
    Main entry point for ingesting a source and processing its contents.

    This function analyzes a source (URL or local path), clones the corresponding repository (if applicable),
    and processes its files according to the specified query parameters. It returns a summary, a tree-like
    structure of the files, and the content of the files. The results can optionally be written to an output file.

    Parameters
    ----------
    source : str
        The source to analyze, which can be a URL (for a Git repository) or a local directory path.
    max_file_size : int
        Maximum allowed file size for file ingestion. Files larger than this size are ignored, by default
        10*1024*1024 (10 MB).
    include_patterns : Union[str, Set[str]], optional
        Pattern or set of patterns specifying which files to include. If `None`, all files are included.
    exclude_patterns : Union[str, Set[str]], optional
        Pattern or set of patterns specifying which files to exclude. If `None`, no files are excluded.
    branch : str, optional
        The branch to clone and ingest. If `None`, the default branch is used.
    token : str, optional
        GitHub personal-access token (PAT). Needed when *source* refers to a
        **private** repository. Can also be set via the ``GITHUB_TOKEN`` env var.
    output : str, optional
        File path where the summary and content should be written. If `None`, the results are not written to a file.

    Returns
    -------
    Tuple[str, str, str]
        A tuple containing:
        - A summary string of the analyzed repository or directory.
        - A tree-like string representation of the file structure.
        - The content of the files in the repository or directory.

    Raises
    ------
    TypeError
        If `clone_repo` does not return a coroutine, or if the `source` is of an unsupported type.
    """
    repo_cloned = False
    clone_dir_used = None

    if not token:
        token = os.getenv("GITHUB_TOKEN")

    try:
        query: IngestionQuery = await parse_query(
            source=source,
            max_file_size=max_file_size,
            from_web=False,
            include_patterns=include_patterns,
            ignore_patterns=exclude_patterns,
        )

        if query.url:
            selected_branch = branch if branch else query.branch  # prioritize branch argument
            query.branch = selected_branch

            clone_config = query.extract_clone_config()
            if temp_clone_dir is not None:
                clone_config.local_path = temp_clone_dir
                query.local_path = Path(temp_clone_dir)
            clone_dir_used = clone_config.local_path
            
            clone_coroutine = clone_repo(clone_config, token=token)

            if inspect.iscoroutine(clone_coroutine):
                if asyncio.get_event_loop().is_running():
                    await clone_coroutine
                else:
                    asyncio.run(clone_coroutine)
            else:
                raise TypeError("clone_repo did not return a coroutine as expected.")

            repo_cloned = True

        summary, tree, content = ingest_query(query)

        if output is not None:
            with open(output, "w", encoding="utf-8") as f:
                f.write(tree + "\n" + content)

        return summary, tree, content
    finally:
        # Clean up the temporary directory if it was created
        if repo_cloned:
            if clone_dir_used is not None:
                shutil.rmtree(clone_dir_used, ignore_errors=True)
            else:
                shutil.rmtree(TMP_BASE_PATH, ignore_errors=True)


def ingest(
    source: str,
    temp_clone_dir: str = None,
    max_file_size: int = 10 * 1024 * 1024,  # 10 MB
    include_patterns: Optional[Union[str, Set[str]]] = None,
    exclude_patterns: Optional[Union[str, Set[str]]] = None,
    branch: Optional[str] = None,
    token: Optional[str] = None,
    output: Optional[str] = None,
) -> Tuple[str, str, str]:
    """
    Synchronous version of ingest_async.

    This function analyzes a source (URL or local path), clones the corresponding repository (if applicable),
    and processes its files according to the specified query parameters. It returns a summary, a tree-like
    structure of the files, and the content of the files. The results can optionally be written to an output file.

    Parameters
    ----------
    source : str
        The source to analyze, which can be a URL (for a Git repository) or a local directory path.
    max_file_size : int
        Maximum allowed file size for file ingestion. Files larger than this size are ignored, by default
        10*1024*1024 (10 MB).
    include_patterns : Union[str, Set[str]], optional
        Pattern or set of patterns specifying which files to include. If `None`, all files are included.
    exclude_patterns : Union[str, Set[str]], optional
        Pattern or set of patterns specifying which files to exclude. If `None`, no files are excluded.
    branch : str, optional
        The branch to clone and ingest. If `None`, the default branch is used.
    token : str, optional
        GitHub personal-access token (PAT). Needed when *source* refers to a
        **private** repository. Can also be set via the ``GITHUB_TOKEN`` env var.
    output : str, optional
        File path where the summary and content should be written. If `None`, the results are not written to a file.

    Returns
    -------
    Tuple[str, str, str]
        A tuple containing:
        - A summary string of the analyzed repository or directory.
        - A tree-like string representation of the file structure.
        - The content of the files in the repository or directory.

    See Also
    --------
    ingest_async : The asynchronous version of this function.
    """
    return asyncio.run(
        ingest_async(
            source=source,
            temp_clone_dir=temp_clone_dir,
            max_file_size=max_file_size,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
            branch=branch,
            token=token,
            output=output,
        )
    )
