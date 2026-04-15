// Elefante Dashboard v2.5.4 - Memory Table with TanStack Table
import { useState, useMemo } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  flexRender,
  createColumnHelper,
  SortingState,
  ColumnFiltersState,
} from '@tanstack/react-table';
import { ChevronUp, ChevronDown, ChevronRight, Search, X } from 'lucide-react';
import type { MemoryNode } from '@/types';

const columnHelper = createColumnHelper<MemoryNode>();

interface MemoryTableProps {
  memories: MemoryNode[];
  onSelectMemory?: (memory: MemoryNode) => void;
  selectedId?: string | null;
}

export function MemoryTable({ memories, onSelectMemory, selectedId }: MemoryTableProps) {
  const [sorting, setSorting] = useState<SortingState>([{ id: 'created_at', desc: true }]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [globalFilter, setGlobalFilter] = useState('');

  const columns = useMemo(() => [
    columnHelper.display({
      id: 'expand',
      header: () => null,
      cell: ({ row }) => (
        <button
          onClick={(e) => {
            e.stopPropagation();
            row.toggleExpanded();
          }}
          className="p-1 hover:bg-slate-700 rounded"
        >
          {row.getIsExpanded() ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
      ),
      size: 32,
    }),
    columnHelper.accessor('properties.title', {
      header: 'Title',
      cell: (info) => (
        <div className="max-w-xs truncate font-medium text-slate-200">
          {info.getValue() || <span className="text-slate-500 italic">Untitled</span>}
        </div>
      ),
      size: 200,
    }),
    columnHelper.accessor('properties.topic', {
      header: 'Topic',
      cell: (info) => {
        const topic = info.getValue();
        return topic ? (
          <span className="px-2 py-0.5 bg-violet-500/20 text-violet-300 rounded text-xs">
            {topic}
          </span>
        ) : null;
      },
      size: 100,
    }),
    columnHelper.accessor('properties.memory_type', {
      header: 'Type',
      cell: (info) => {
        const type = info.getValue();
        const typeColors: Record<string, string> = {
          fact: 'bg-cyan-500/20 text-cyan-300',
          decision: 'bg-amber-500/20 text-amber-300',
          preference: 'bg-pink-500/20 text-pink-300',
          insight: 'bg-emerald-500/20 text-emerald-300',
        };
        return type ? (
          <span className={`px-2 py-0.5 rounded text-xs ${typeColors[type] || 'bg-slate-500/20 text-slate-300'}`}>
            {type}
          </span>
        ) : null;
      },
      size: 80,
    }),
    columnHelper.accessor('created_at', {
      header: 'Created',
      cell: (info) => {
        const date = info.getValue();
        if (!date) return null;
        return (
          <span className="text-xs text-slate-400">
            {new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
          </span>
        );
      },
      size: 100,
    }),
    columnHelper.accessor('properties.score', {
      header: 'Vitality',
      cell: (info) => {
        const score = info.getValue();
        if (score === undefined || score === null) return null;
        const n = typeof score === 'number' ? score : Number(score);
        const [label, cls] =
          n >= 80 ? ['Fresh',   'bg-emerald-500/20 text-emerald-300'] :
          n >= 60 ? ['Healthy', 'bg-teal-500/20 text-teal-300'] :
          n >= 40 ? ['Aging',   'bg-amber-500/20 text-amber-300'] :
          n >= 20 ? ['Fading',  'bg-orange-500/20 text-orange-300'] :
                    ['Dormant', 'bg-red-500/20 text-red-400'];
        return (
          <span className={`px-2 py-0.5 rounded text-xs ${cls}`}>
            {label}
          </span>
        );
      },
      size: 72,
    }),
    columnHelper.accessor('properties.access_count', {
      header: 'Uses',
      cell: (info) => {
        const count = Number(info.getValue()) || 0;
        if (count === 0) {
          return <span className="px-1.5 py-0.5 bg-red-500/15 text-red-400 rounded text-xs">Never</span>;
        }
        if (count >= 10) {
          return <span className="px-1.5 py-0.5 bg-emerald-500/15 text-emerald-400 rounded text-xs">{count}</span>;
        }
        return <span className="text-xs text-slate-400">{count}</span>;
      },
      size: 60,
    }),
  ], []);

  const table = useReactTable({
    data: memories,
    columns,
    state: {
      sorting,
      columnFilters,
      globalFilter,
    },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getRowId: (row) => row.id,
  });

  return (
    <div className="flex flex-col h-full">
      {/* Search/Filter Bar */}
      <div className="p-3 border-b border-slate-700/60 bg-slate-800/40">
        <div className="flex items-center gap-3">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={16} />
            <input
              type="text"
              value={globalFilter}
              onChange={(e) => setGlobalFilter(e.target.value)}
              placeholder="Filter memories..."
              className="w-full pl-9 pr-8 py-2 bg-slate-900/60 border border-slate-700/60 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
            />
            {globalFilter && (
              <button
                onClick={() => setGlobalFilter('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 hover:bg-slate-700 rounded"
              >
                <X size={14} className="text-slate-400" />
              </button>
            )}
          </div>
          <div className="text-xs text-slate-500">
            {table.getFilteredRowModel().rows.length} of {memories.length} memories
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-slate-900/90 backdrop-blur z-10">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id} className="border-b border-slate-700/60">
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className="px-3 py-2 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider"
                    style={{ width: header.getSize() !== 150 ? header.getSize() : undefined }}
                  >
                    {header.isPlaceholder ? null : (
                      <button
                        onClick={header.column.getToggleSortingHandler()}
                        className="flex items-center gap-1 hover:text-slate-200 transition-colors"
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {header.column.getIsSorted() === 'asc' && <ChevronUp size={12} />}
                        {header.column.getIsSorted() === 'desc' && <ChevronDown size={12} />}
                      </button>
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <>
                <tr
                  key={row.id}
                  onClick={() => onSelectMemory?.(row.original)}
                  className={
                    'border-b border-slate-800/40 cursor-pointer transition-colors ' +
                    (selectedId === row.id
                      ? 'bg-cyan-500/10 hover:bg-cyan-500/15'
                      : 'hover:bg-slate-800/60')
                  }
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-3 py-2">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
                {row.getIsExpanded() && (
                  <tr key={`${row.id}-expanded`} className="bg-slate-800/30">
                    <td colSpan={row.getVisibleCells().length} className="px-4 py-4">
                      <div className="space-y-3">
                        {/* TITLE — scannable label */}
                        {row.original.properties.title && (
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">Title</span>
                            <span className="text-sm font-semibold text-cyan-300">{row.original.properties.title}</span>
                          </div>
                        )}
                        {/* DIVIDER */}
                        <div className="border-t border-slate-700/50" />
                        {/* BODY — the actual knowledge */}
                        <div>
                          <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-500 block mb-1">Body</span>
                          <div className="text-slate-300 text-sm leading-relaxed whitespace-pre-wrap">
                            {row.original.properties.content}
                          </div>
                        </div>
                        {/* META */}
                        <div className="flex flex-wrap gap-4 text-xs text-slate-500 pt-1 border-t border-slate-700/30">
                          <div><span className="text-slate-600">ID:</span> <code className="text-slate-400">{row.original.id}</code></div>
                          {row.original.properties.tags && (
                            <div><span className="text-slate-600">Tags:</span> {row.original.properties.tags}</div>
                          )}
                          {row.original.properties.source && (
                            <div><span className="text-slate-600">Source:</span> {row.original.properties.source}</div>
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>

        {table.getFilteredRowModel().rows.length === 0 && (
          <div className="flex items-center justify-center py-12 text-slate-500">
            {globalFilter ? 'No memories match your filter' : 'No memories found'}
          </div>
        )}
      </div>
    </div>
  );
}