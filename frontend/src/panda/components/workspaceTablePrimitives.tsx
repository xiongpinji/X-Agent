import React from 'react'

export function WorkspaceTableHeader({ columns }: { columns: readonly string[] }) {
  return (
    <thead>
      <tr>
        {columns.map((column) => (
          <th key={column}>{column}</th>
        ))}
      </tr>
    </thead>
  )
}

export function WorkspaceTable({ columns, children }: { columns: readonly string[]; children: React.ReactNode }) {
  return (
    <table className="panda-table">
      <WorkspaceTableHeader columns={columns} />
      <tbody>{children}</tbody>
    </table>
  )
}
