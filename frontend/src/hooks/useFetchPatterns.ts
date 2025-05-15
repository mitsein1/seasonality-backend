import { useQuery } from 'react-query';
import { fetchStrategies, ScreenerFilters, StrategySummary } from '../services/api';

/**
 * Hook to fetch strategy patterns with given filters.
 * Uses react-query for caching, auto-refetch, and status handling.
 * @param filters - Screener filter parameters (patternType, yearsBack, etc.)
 */
export function useFetchPatterns(filters: ScreenerFilters) {
  // Create a stable query key including filters
  const queryKey = ['screener', filters];

  const query = useQuery<StrategySummary[], Error>(
    queryKey,
    () => fetchStrategies(filters),
    {
      keepPreviousData: true,
      staleTime: 1000 * 60 * 5, // 5 minutes cache
      refetchOnWindowFocus: false,
    }
  );

  return {
    data: query.data ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}
