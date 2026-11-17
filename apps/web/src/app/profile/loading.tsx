import { Loading, Skeleton } from "@/components/ui/skeleton";

import "./profile.css";

/** S-H6 while the profile is read (C-SKELETON): bars at the size of the head, the points and the settings. */
export default function ProfileLoading() {
  return (
    <div className="pf">
      <Loading what="Loading your profile">
        <div className="pf-head">
          <Skeleton width={72} height={72} style={{ borderRadius: "50%" }} />
          <div>
            <Skeleton width={240} height={36} />
            <Skeleton width={300} height={16} style={{ marginTop: 10 }} />
          </div>
        </div>
        <div className="pf-grid">
          <div className="pf-card">
            <Skeleton width="40%" height={14} />
            <Skeleton width="50%" height={56} style={{ marginTop: 16 }} />
            <Skeleton height={14} style={{ marginTop: 14 }} />
          </div>
          <div className="pf-set">
            {[0, 1].map((i) => (
              <div key={i} className="pf-card">
                <Skeleton width="30%" height={14} />
                <Skeleton width="60%" height={16} style={{ marginTop: 16 }} />
                <Skeleton width="85%" height={14} style={{ marginTop: 10 }} />
              </div>
            ))}
          </div>
        </div>
      </Loading>
    </div>
  );
}
