declare module 'frappe-gantt' {
  interface GanttTask {
    id: string
    name: string
    start: string
    end: string
    progress: number
    dependencies?: string
  }

  interface GanttOptions {
    view_mode?: 'Hour' | 'Quarter Day' | 'Half Day' | 'Day' | 'Week' | 'Month' | 'Year'
    language?: string
    readonly?: boolean
    scroll_to?: string
    today_button?: boolean
    popup?: false
    bar_height?: number
    on_click?: (task: GanttTask) => void
  }

  export default class Gantt {
    constructor(element: HTMLElement, tasks: GanttTask[], options?: GanttOptions)
  }
}
