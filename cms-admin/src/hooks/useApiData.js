import { useEffect, useState } from 'react'

export function useApiData(loader) {
  const [state, setState] = useState({ loading: true, data: null, error: null })

  useEffect(() => {
    let active = true
    loader().then(
      (data) => { if (active) setState({ loading: false, data, error: null }) },
      (error) => { if (active) setState({ loading: false, data: null, error }) },
    )
    return () => { active = false }
  }, [loader])

  return state
}
