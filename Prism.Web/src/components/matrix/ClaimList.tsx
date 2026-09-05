import type { ClaimDto } from "@/types/api";
import { ClaimRow } from "@/components/matrix/ClaimRow";
import { AbsenceRow } from "@/components/matrix/AbsenceRow";

interface ClaimListProps {
  claims: ClaimDto[];
  onViewEvidence: (claimId: string) => void;
}

export function ClaimList({ claims, onViewEvidence }: ClaimListProps) {
  return (
    <div className="space-y-2 md:space-y-3">
      {claims.map((claim) =>
        claim.missing ? (
          <AbsenceRow key={claim.id} claim={claim} onViewEvidence={() => onViewEvidence(claim.id)} />
        ) : (
          <ClaimRow key={claim.id} claim={claim} onViewEvidence={() => onViewEvidence(claim.id)} />
        )
      )}
    </div>
  );
}
