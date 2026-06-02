import React from 'react'
import clsx from 'clsx'

export interface DataTableProps<T extends Record<string, any>> {
  columns: Array<{
    key: keyof T
    label: string
    render?: (value: any, row: T) => React.ReactNode
    width?: string
  }>
  data: T[]
  isLoading?: boolean
  onRowClick?: (row: T) => void
  striped?: boolean
}

export const DataTable = React.forwardRef<HTMLDivElement, DataTableProps<any>>(
  ({ columns, data, isLoading = false, onRowClick, striped = true }, ref) => {
    if (isLoading) {
      return (
        <div className="p-8 text-center">
          <p className="text-slate-600 dark:text-slate-400">Loading...</p>
        </div>
      )
    }

    if (data.length === 0) {
      return (
        <div className="p-8 text-center">
          <p className="text-slate-600 dark:text-slate-400">No data available</p>
        </div>
      )
    }

    return (
      <div
        ref={ref}
        className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700"
      >
        <table className="w-full">
          <thead className="bg-slate-50 dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700">
            <tr>
              {columns.map((column) => (
                <th
                  key={String(column.key)}
                  className={clsx(
                    'px-6 py-3 text-left text-sm font-semibold text-slate-900 dark:text-white',
                    column.width
                  )}
                >
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, rowIndex) => (
              <tr
                key={rowIndex}
                className={clsx(
                  'border-b border-slate-200 dark:border-slate-700 transition-colors',
                  striped && rowIndex % 2 === 0
                    ? 'bg-slate-50 dark:bg-slate-900/50'
                    : 'bg-white dark:bg-slate-900',
                  onRowClick && 'hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer'
                )}
                onClick={() => onRowClick?.(row)}
              >
                {columns.map((column) => (
                  <td
                    key={String(column.key)}
                    className="px-6 py-4 text-sm text-slate-900 dark:text-white"
                  >
                    {column.render
                      ? column.render(row[column.key], row)
                      : String(row[column.key])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }
)

DataTable.displayName = 'DataTable'
