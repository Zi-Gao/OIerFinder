import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Button } from "@/components/ui/button";
import { Check, Copy, Sparkles, AlertCircle, Braces, Tag, Quote } from "lucide-react";
import { cn } from "@/lib/utils";

// Schema definition for OIerFinder JSON search queries
const SCHEMA_SUGGESTIONS = [
  // Root level properties
  {
    label: 'record_filters',
    kind: 'property',
    detail: 'Array of award record conditions',
    context: 'root',
    insertText: '"record_filters": [\n    {\n      $0\n    }\n  ]',
  },
  {
    label: 'oier_filters',
    kind: 'property',
    detail: 'Programmer demographic & enrollment filters',
    context: 'root',
    insertText: '"oier_filters": {\n    $0\n  }',
  },
  {
    label: 'limit',
    kind: 'property',
    detail: 'Maximum number of results (1-100)',
    context: 'root',
    insertText: '"limit": 10',
  },

  // Record Filter Properties
  {
    label: 'contest_type',
    kind: 'property',
    detail: 'Contest type (e.g. CSP提高, NOIP, NOI)',
    context: 'record',
    insertText: '"contest_type": "$0"',
  },
  {
    label: 'level',
    kind: 'property',
    detail: 'Award medal/level (e.g. 一等奖, 金牌)',
    context: 'record',
    insertText: '"level": "$0"',
  },
  {
    label: 'year',
    kind: 'property',
    detail: 'Contest year (e.g. 2023)',
    context: 'record',
    insertText: '"year": 2023',
  },
  {
    label: 'year_start',
    kind: 'property',
    detail: 'Starting year for range search',
    context: 'record',
    insertText: '"year_start": 2020',
  },
  {
    label: 'year_end',
    kind: 'property',
    detail: 'Ending year for range search',
    context: 'record',
    insertText: '"year_end": 2024',
  },
  {
    label: 'provinces',
    kind: 'property',
    detail: 'Province names (e.g. ["北京", "上海"])',
    context: 'record',
    insertText: '"provinces": "$0"',
  },
  {
    label: 'min_score',
    kind: 'property',
    detail: 'Minimum score threshold',
    context: 'record',
    insertText: '"min_score": 100',
  },
  {
    label: 'max_score',
    kind: 'property',
    detail: 'Maximum score threshold',
    context: 'record',
    insertText: '"max_score": 400',
  },
  {
    label: 'min_rank',
    kind: 'property',
    detail: 'Minimum rank in contest',
    context: 'record',
    insertText: '"min_rank": 1',
  },
  {
    label: 'max_rank',
    kind: 'property',
    detail: 'Maximum rank in contest',
    context: 'record',
    insertText: '"max_rank": 50',
  },
  {
    label: 'fall_semester',
    kind: 'property',
    detail: 'Fall semester only (boolean: true/false)',
    context: 'record',
    insertText: '"fall_semester": true',
  },
  {
    label: 'years',
    kind: 'property',
    detail: 'Specific years list (e.g. [2022, 2023])',
    context: 'record',
    insertText: '"years": [2022, 2023]',
  },
  {
    label: 'contest_ids',
    kind: 'property',
    detail: 'Specific contest IDs list',
    context: 'record',
    insertText: '"contest_ids": [101, 102]',
  },
  {
    label: 'school_ids',
    kind: 'property',
    detail: 'Specific school IDs list',
    context: 'record',
    insertText: '"school_ids": [233, 234]',
  },

  // OIer Filter Properties
  {
    label: 'initials',
    kind: 'property',
    detail: 'Pinyin initials (e.g. "QZH", "DMY")',
    context: 'oier',
    insertText: '"initials": "$0"',
  },
  {
    label: 'gender',
    kind: 'property',
    detail: 'Gender: 1 for Male, -1 for Female',
    context: 'oier',
    insertText: '"gender": 1',
  },
  {
    label: 'enroll_min',
    kind: 'property',
    detail: 'Minimum middle school enrollment year',
    context: 'oier',
    insertText: '"enroll_min": 2020',
  },
  {
    label: 'enroll_max',
    kind: 'property',
    detail: 'Maximum middle school enrollment year',
    context: 'oier',
    insertText: '"enroll_max": 2026',
  },

  // Values: Contest Types
  ...["CSP入门", "CSP提高", "NOIP普及", "NOIP提高", "NOIP", "WC", "NOID类", "NOI", "APIO", "CTSC"].map(c => ({
    label: c,
    kind: 'value',
    detail: `Contest type: ${c}`,
    context: 'contest_type',
    insertText: `"${c}"`,
  })),

  // Values: Award Levels
  ...["金牌", "银牌", "铜牌", "一等奖", "二等奖", "三等奖"].map(l => ({
    label: l,
    kind: 'value',
    detail: `Prize level: ${l}`,
    context: 'level',
    insertText: `"${l}"`,
  })),

  // Values: Booleans & Genders
  { label: 'true', kind: 'value', detail: 'Boolean true', context: 'value', insertText: 'true' },
  { label: 'false', kind: 'value', detail: 'Boolean false', context: 'value', insertText: 'false' },
  { label: '1 (Male)', kind: 'value', detail: 'Male gender code', context: 'gender', insertText: '1' },
  { label: '-1 (Female)', kind: 'value', detail: 'Female gender code', context: 'gender', insertText: '-1' },

  // Quick Snippets
  {
    label: 'record filter item',
    kind: 'snippet',
    detail: 'Add a new record filter condition object',
    context: 'snippet',
    insertText: '{\n      "contest_type": "$0",\n      "level": ""\n    }',
  },
  {
    label: 'full query template',
    kind: 'snippet',
    detail: 'Standard complete search query template',
    context: 'snippet',
    insertText: '{\n  "record_filters": [\n    {\n      "contest_type": "CSP提高",\n      "level": "一等奖"\n    }\n  ],\n  "oier_filters": {},\n  "limit": 10\n}',
  }
];

// Highlight JSON code into HTML tokens
function highlightJson(json) {
  if (!json) return '';
  const escaped = json
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  return escaped.replace(
    /("(?:\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"\n])*"?)(:\s*)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|([{}[\],])/g,
    (match, str, colon, boolOrNull, punct) => {
      if (str) {
        if (colon) {
          // Object key: Vibrant blue/cyan
          return `<span class="text-sky-600 dark:text-sky-400 font-semibold">${str}</span>${colon}`;
        }
        // String value: Vibrant emerald green
        return `<span class="text-emerald-600 dark:text-emerald-400">${str}</span>`;
      }
      if (boolOrNull) {
        if (boolOrNull === 'null') {
          return `<span class="text-slate-400 italic">${boolOrNull}</span>`;
        }
        // Boolean: Purple/violet
        return `<span class="text-purple-600 dark:text-purple-400 font-semibold">${boolOrNull}</span>`;
      }
      if (punct) {
        // Brackets, commas, colons
        return `<span class="text-muted-foreground/60">${punct}</span>`;
      }
      // Numbers: Amber/orange
      return `<span class="text-amber-600 dark:text-amber-400 font-semibold">${match}</span>`;
    }
  );
}

function JsonEditor({ value, onChange, onFormat, rows = 16, className }) {
  const [copied, setCopied] = useState(false);
  const [jsonError, setJsonError] = useState(null);
  const [cursorPos, setCursorPos] = useState(0);
  const [mounted, setMounted] = useState(false);

  // Autocomplete state
  const [suggestions, setSuggestions] = useState([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [menuPosition, setMenuPosition] = useState(null);
  const [showMenu, setShowMenu] = useState(false);

  const textareaRef = useRef(null);
  const preRef = useRef(null);
  const lineGutterRef = useRef(null);
  const containerRef = useRef(null);
  const menuRef = useRef(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Validate JSON on changes
  useEffect(() => {
    try {
      if (value.trim()) {
        JSON.parse(value);
      }
      setJsonError(null);
    } catch (err) {
      setJsonError(err.message);
    }
  }, [value]);

  // Close suggestion menu on click outside or window resize
  useEffect(() => {
    if (!showMenu) return;
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target) && textareaRef.current !== e.target) {
        setShowMenu(false);
      }
    };
    const handleResize = () => {
      setShowMenu(false);
    };
    window.addEventListener('mousedown', handleClickOutside);
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('mousedown', handleClickOutside);
      window.removeEventListener('resize', handleResize);
    };
  }, [showMenu]);

  // Synchronize scrolling
  const handleScroll = () => {
    if (!textareaRef.current) return;
    const { scrollTop, scrollLeft } = textareaRef.current;
    if (preRef.current) {
      preRef.current.scrollTop = scrollTop;
      preRef.current.scrollLeft = scrollLeft;
    }
    if (lineGutterRef.current) {
      lineGutterRef.current.scrollTop = scrollTop;
    }
    if (showMenu) {
      setShowMenu(false);
    }
  };

  // Generate line numbers
  const lineCount = useMemo(() => {
    return (value || '').split('\n').length;
  }, [value]);

  // Compute context & filter suggestions based on cursor position
  const updateSuggestions = useCallback((text, pos) => {
    const textBefore = text.slice(0, pos);
    const lines = textBefore.split('\n');
    const currentLine = lines[lines.length - 1];

    // Find current word/token being typed
    const match = currentLine.match(/([a-zA-Z0-9_\-\u4e00-\u9fa5]+|"[a-zA-Z0-9_\-\u4e00-\u9fa5]*)$/);
    const query = match ? match[1].replace(/^"/, '').toLowerCase() : '';

    // Detect context
    let activeContext = 'all';
    if (/"contest_type"\s*:\s*"?[^"]*$/.test(currentLine)) {
      activeContext = 'contest_type';
    } else if (/"level"\s*:\s*"?[^"]*$/.test(currentLine)) {
      activeContext = 'level';
    } else if (/"gender"\s*:\s*$/.test(currentLine)) {
      activeContext = 'gender';
    } else if (/"fall_semester"\s*:\s*$/.test(currentLine)) {
      activeContext = 'value';
    } else if (textBefore.lastIndexOf('record_filters') > textBefore.lastIndexOf('oier_filters')) {
      activeContext = 'record';
    } else if (textBefore.lastIndexOf('oier_filters') > textBefore.lastIndexOf('record_filters')) {
      activeContext = 'oier';
    } else {
      activeContext = 'root';
    }

    let filtered = SCHEMA_SUGGESTIONS.filter(item => {
      // Prioritize contextual matches or general queries
      if (activeContext === 'contest_type') {
        return item.context === 'contest_type';
      }
      if (activeContext === 'level') {
        return item.context === 'level';
      }
      if (activeContext === 'gender') {
        return item.context === 'gender';
      }
      if (activeContext === 'value') {
        return item.context === 'value';
      }

      // In record context, prioritize record properties & snippets
      if (activeContext === 'record') {
        if (item.context === 'record' || item.context === 'snippet') return true;
      }
      // In oier context, prioritize oier properties
      if (activeContext === 'oier') {
        if (item.context === 'oier') return true;
      }
      // In root context, prioritize root properties
      if (activeContext === 'root') {
        if (item.context === 'root' || item.context === 'snippet') return true;
      }

      return true;
    });

    if (query) {
      filtered = filtered.filter(item =>
        item.label.toLowerCase().includes(query) ||
        item.detail.toLowerCase().includes(query)
      );
    }

    if (filtered.length > 0 && (query.length > 0 || currentLine.trim().endsWith(':') || currentLine.trim().endsWith('{"') || currentLine.trim().endsWith('",'))) {
      setSuggestions(filtered.slice(0, 8));
      setSelectedIndex(0);

      const textarea = textareaRef.current;
      if (!textarea) return;
      const rect = textarea.getBoundingClientRect();

      const lineIndex = lines.length - 1;
      const colIndex = currentLine.length;
      const charWidth = 8.42;
      const lineHeight = 24;

      const cursorY = rect.top + 16 + lineIndex * lineHeight - textarea.scrollTop;
      const cursorX = rect.left + 12 + colIndex * charWidth - textarea.scrollLeft;

      const menuWidth = 288;
      const menuHeight = 224;

      const spaceBelow = window.innerHeight - (cursorY + lineHeight);
      const showAbove = spaceBelow < menuHeight && cursorY > menuHeight;

      let top = showAbove
        ? cursorY - menuHeight - 6
        : cursorY + lineHeight + 4;
      top = Math.max(8, Math.min(top, window.innerHeight - menuHeight - 8));

      let left = cursorX;
      if (left + menuWidth > window.innerWidth - 16) {
        left = window.innerWidth - menuWidth - 16;
      }
      left = Math.max(16, left);

      setMenuPosition({ top, left });
      setShowMenu(true);
    } else {
      setShowMenu(false);
    }
  }, []);

  // Insert a suggestion into the editor text
  const applySuggestion = useCallback((item) => {
    if (!textareaRef.current) return;
    const text = value;
    const pos = cursorPos;
    const textBefore = text.slice(0, pos);
    const lines = textBefore.split('\n');
    const currentLine = lines[lines.length - 1];

    const match = currentLine.match(/([a-zA-Z0-9_\-\u4e00-\u9fa5]+|"[a-zA-Z0-9_\-\u4e00-\u9fa5]*)$/);
    const tokenStart = match ? pos - match[1].length : pos;
    let tokenEnd = pos;

    let insert = item.insertText;
    // Absorb existing closing quote if insertion ends with one and next char is one
    if (insert.endsWith('"') && text.slice(tokenEnd).startsWith('"')) {
      tokenEnd += 1;
    }

    let newPos = tokenStart + insert.length;
    if (insert.includes('$0')) {
      const parts = insert.split('$0');
      insert = parts[0] + parts[1];
      newPos = tokenStart + parts[0].length;
    }

    const nextValue = text.slice(0, tokenStart) + insert + text.slice(tokenEnd);
    onChange(nextValue);
    setShowMenu(false);

    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
        textareaRef.current.setSelectionRange(newPos, newPos);
        setCursorPos(newPos);
      }
    }, 0);
  }, [value, cursorPos, onChange]);

  // Handle typing & auto-closing brackets/quotes
  const handleKeyDown = (e) => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = value.slice(start, end);

    // If autocomplete menu is active
    if (showMenu && suggestions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex(prev => (prev + 1) % suggestions.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex(prev => (prev - 1 + suggestions.length) % suggestions.length);
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        applySuggestion(suggestions[selectedIndex]);
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        setShowMenu(false);
        return;
      }
    }

    // Manual trigger for autocomplete (Ctrl+Space or Cmd+Space)
    if ((e.ctrlKey || e.metaKey) && e.key === ' ') {
      e.preventDefault();
      updateSuggestions(value, start);
      return;
    }

    // Auto-closing quotes
    if (e.key === '"') {
      if (start === end && value[start] === '"') {
        // Step over closing quote
        e.preventDefault();
        textarea.setSelectionRange(start + 1, start + 1);
        setCursorPos(start + 1);
        return;
      }
      e.preventDefault();
      const nextValue = value.slice(0, start) + `"${selectedText}"` + value.slice(end);
      onChange(nextValue);
      setTimeout(() => {
        textarea.setSelectionRange(start + 1, start + 1 + selectedText.length);
        setCursorPos(start + 1);
      }, 0);
      return;
    }

    // Auto-closing braces {}
    if (e.key === '{') {
      e.preventDefault();
      const nextValue = value.slice(0, start) + `{${selectedText}}` + value.slice(end);
      onChange(nextValue);
      setTimeout(() => {
        textarea.setSelectionRange(start + 1, start + 1 + selectedText.length);
        setCursorPos(start + 1);
      }, 0);
      return;
    }

    // Auto-closing brackets []
    if (e.key === '[') {
      e.preventDefault();
      const nextValue = value.slice(0, start) + `[${selectedText}]` + value.slice(end);
      onChange(nextValue);
      setTimeout(() => {
        textarea.setSelectionRange(start + 1, start + 1 + selectedText.length);
        setCursorPos(start + 1);
      }, 0);
      return;
    }

    // Smart backspace removing pair
    if (e.key === 'Backspace' && start === end && start > 0) {
      const prevChar = value[start - 1];
      const nextChar = value[start];
      if (
        (prevChar === '{' && nextChar === '}') ||
        (prevChar === '[' && nextChar === ']') ||
        (prevChar === '"' && nextChar === '"')
      ) {
        e.preventDefault();
        const nextValue = value.slice(0, start - 1) + value.slice(start + 1);
        onChange(nextValue);
        setTimeout(() => {
          textarea.setSelectionRange(start - 1, start - 1);
          setCursorPos(start - 1);
        }, 0);
        return;
      }
    }

    // Tab key inserts 2 spaces
    if (e.key === 'Tab') {
      e.preventDefault();
      const indent = '  ';
      const nextValue = value.slice(0, start) + indent + value.slice(end);
      onChange(nextValue);
      setTimeout(() => {
        textarea.setSelectionRange(start + 2, start + 2);
        setCursorPos(start + 2);
      }, 0);
      return;
    }

    // Enter key with smart indentation
    if (e.key === 'Enter') {
      const lineBefore = value.slice(0, start).split('\n').pop() || '';
      const indentMatch = lineBefore.match(/^\s*/);
      let currentIndent = indentMatch ? indentMatch[0] : '';
      const charBefore = value[start - 1];
      const charAfter = value[start];

      if ((charBefore === '{' && charAfter === '}') || (charBefore === '[' && charAfter === ']')) {
        e.preventDefault();
        const extraIndent = currentIndent + '  ';
        const insertion = `\n${extraIndent}\n${currentIndent}`;
        const nextValue = value.slice(0, start) + insertion + value.slice(end);
        onChange(nextValue);
        setTimeout(() => {
          const newPos = start + extraIndent.length + 1;
          textarea.setSelectionRange(newPos, newPos);
          setCursorPos(newPos);
        }, 0);
        return;
      }

      if (charBefore === '{' || charBefore === '[') {
        currentIndent += '  ';
      }

      e.preventDefault();
      const nextValue = value.slice(0, start) + '\n' + currentIndent + value.slice(end);
      onChange(nextValue);
      setTimeout(() => {
        const newPos = start + currentIndent.length + 1;
        textarea.setSelectionRange(newPos, newPos);
        setCursorPos(newPos);
      }, 0);
      return;
    }
  };

  const handleChange = (e) => {
    const nextVal = e.target.value;
    const pos = e.target.selectionStart;
    onChange(nextVal);
    setCursorPos(pos);
    updateSuggestions(nextVal, pos);
  };

  const handleSelect = (e) => {
    const pos = e.target.selectionStart;
    setCursorPos(pos);
  };

  // Prettify / Format JSON action
  const handlePrettify = () => {
    try {
      const parsed = JSON.parse(value);
      const formatted = JSON.stringify(parsed, null, 2);
      onChange(formatted);
      if (onFormat) onFormat(formatted);
    } catch {
      // Ignore if currently invalid JSON
    }
  };

  // Copy to clipboard
  const handleCopy = () => {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className={cn("flex flex-col border border-muted/50 rounded-2xl overflow-hidden bg-background shadow-sm", className)}>
      {/* Editor Sub-Header Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 bg-muted/20 border-b border-muted/30">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs font-bold text-foreground">
            <Braces className="size-3.5 text-primary" />
            <span>JSON Editor</span>
          </div>

          {/* Validation Status Indicator */}
          {jsonError ? (
            <div className="flex items-center gap-1.5 text-[10px] text-destructive font-medium bg-destructive/10 px-2 py-0.5 rounded-full max-w-[280px] truncate" title={jsonError}>
              <AlertCircle className="size-3 shrink-0" />
              <span className="truncate">Syntax Error</span>
            </div>
          ) : (
            <div className="flex items-center gap-1 text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold bg-emerald-500/10 px-2 py-0.5 rounded-full">
              <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span>Valid JSON</span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-1.5">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handlePrettify}
            disabled={!!jsonError}
            className="h-7 px-2.5 text-[10px] font-bold uppercase tracking-wider text-muted-foreground hover:text-primary gap-1"
            title="Prettify / Format JSON (2 spaces)"
          >
            <Sparkles className="size-3" />
            Format
          </Button>

          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleCopy}
            className="h-7 px-2.5 text-[10px] font-bold uppercase tracking-wider text-muted-foreground hover:text-primary gap-1"
            title="Copy JSON Payload"
          >
            {copied ? <Check className="size-3 text-emerald-500" /> : <Copy className="size-3" />}
            {copied ? "Copied" : "Copy"}
          </Button>
        </div>
      </div>

      {/* Editor Body Area */}
      <div ref={containerRef} className="relative flex min-h-[380px] bg-background text-sm font-mono overflow-hidden">
        {/* Line Numbers Gutter */}
        <div
          ref={lineGutterRef}
          aria-hidden="true"
          className="w-11 shrink-0 py-4 select-none bg-muted/10 border-r border-muted/20 text-muted-foreground/35 text-right pr-2.5 text-xs font-mono leading-6 overflow-hidden"
        >
          {Array.from({ length: lineCount }, (_, i) => (
            <div key={i + 1}>{i + 1}</div>
          ))}
        </div>

        {/* Code & Input Canvas */}
        <div className="relative flex-1 overflow-hidden">
          {/* Syntax Highlighted Overlay (Underneath) */}
          <pre
            ref={preRef}
            aria-hidden="true"
            tabIndex={-1}
            dangerouslySetInnerHTML={{ __html: highlightJson(value) + '<br/>' }}
            className="absolute inset-0 m-0 py-4 px-3 font-mono text-sm leading-6 tracking-normal whitespace-pre overflow-hidden pointer-events-none select-none"
            style={{ tabSize: 2, MozTabSize: 2 }}
          />

          {/* Interactive Textarea (On Top) */}
          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleChange}
            onSelect={handleSelect}
            onKeyDown={handleKeyDown}
            onScroll={handleScroll}
            onClick={() => setShowMenu(false)}
            rows={rows}
            spellCheck={false}
            autoCapitalize="off"
            autoComplete="off"
            autoCorrect="off"
            className="absolute inset-0 m-0 py-4 px-3 w-full h-full font-mono text-sm leading-6 tracking-normal text-transparent caret-foreground bg-transparent resize-none border-none outline-none focus:ring-0 focus:outline-none whitespace-pre overflow-auto z-10 selection:bg-primary/20"
            style={{ tabSize: 2, MozTabSize: 2 }}
          />

          {/* Autocomplete Suggestions Menu (Rendered via Portal at top-most stacking context) */}
          {mounted && showMenu && suggestions.length > 0 && menuPosition && createPortal(
            <div
              ref={menuRef}
              className="fixed z-[99999] w-72 max-h-56 bg-popover/95 text-popover-foreground backdrop-blur-md border border-muted/80 shadow-2xl rounded-xl p-1 overflow-y-auto animate-in fade-in zoom-in-95 duration-100 ring-1 ring-black/10 dark:ring-white/10"
              style={{
                top: `${menuPosition.top}px`,
                left: `${menuPosition.left}px`,
              }}
            >
              <div className="px-2 py-1 text-[9px] font-bold uppercase tracking-wider text-muted-foreground/60 border-b border-muted/20 flex items-center justify-between">
                <span>Suggestions</span>
                <span className="text-[8px] opacity-70">Tab / Enter</span>
              </div>
              <div className="mt-1 space-y-0.5">
                {suggestions.map((item, idx) => {
                  const isSelected = idx === selectedIndex;
                  return (
                    <button
                      key={item.label + idx}
                      type="button"
                      onMouseDown={(e) => {
                        e.preventDefault();
                        applySuggestion(item);
                      }}
                      className={cn(
                        "w-full text-left px-2 py-1.5 rounded-lg flex items-center justify-between text-xs transition-colors",
                        isSelected
                          ? "bg-primary text-primary-foreground font-semibold shadow-sm"
                          : "hover:bg-muted/50 text-foreground"
                      )}
                    >
                      <div className="flex items-center gap-2 truncate">
                        {item.kind === 'property' && <Tag className={cn("size-3 shrink-0", isSelected ? "text-primary-foreground" : "text-sky-500")} />}
                        {item.kind === 'value' && <Quote className={cn("size-3 shrink-0", isSelected ? "text-primary-foreground" : "text-emerald-500")} />}
                        {item.kind === 'snippet' && <Sparkles className={cn("size-3 shrink-0", isSelected ? "text-primary-foreground" : "text-amber-500")} />}
                        <span className="font-mono truncate">{item.label}</span>
                      </div>
                      <span className={cn("text-[10px] ml-2 shrink-0 truncate max-w-[100px]", isSelected ? "text-primary-foreground/80" : "text-muted-foreground/60")}>
                        {item.detail}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>,
            document.body
          )}
        </div>
      </div>

      {/* Editor Footer Hints */}
      <div className="flex items-center justify-between px-4 py-1.5 bg-muted/10 border-t border-muted/20 text-[10px] text-muted-foreground/60">
        <div className="flex items-center gap-3">
          <span>{lineCount} lines</span>
          <span>•</span>
          <span>Tab: 2 spaces</span>
          <span>•</span>
          <span>Ctrl+Space: Suggestions</span>
        </div>
        <div>
          <span>JSON Schema Enabled</span>
        </div>
      </div>
    </div>
  );
}

export default JsonEditor;
