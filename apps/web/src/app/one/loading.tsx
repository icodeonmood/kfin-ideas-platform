import { Loading, Skeleton } from "@/components/ui/skeleton";

import "./one.css";

/**
 * S-ONE while the dashboard is read (C-SKELETON): bars at the size of the hero, the two cards and the four figures,
 * with one polite line saying what is loading. Never a full-screen loader (C-SKELETON/5).
 */
export default function OneLoading() {
  return (
    <div className="on">
      <Loading what="Loading your One dashboard">
        <div className="on-crumb">
          <Skeleton width={200} height={14} style={{ margin: "15px 0 35px" }} />
        </div>
        <div className="slab on-slab">
          <div className="on-hero">
            <Skeleton height={300} style={{ opacity: 0.12 }} />
            <div>
              <Skeleton width="70%" height={64} style={{ opacity: 0.12 }} />
              <Skeleton width="50%" height={18} style={{ marginTop: 24, opacity: 0.12 }} />
            </div>
          </div>
        </div>
        <div className="on-g2">
          {[0, 1].map((i) => (
            <div key={i} className="card on-card">
              <Skeleton width="40%" height={24} />
              <Skeleton height={14} style={{ marginTop: 18 }} />
              <Skeleton width="80%" height={14} style={{ marginTop: 10 }} />
              <Skeleton width={240} height={52} style={{ marginTop: 22 }} />
            </div>
          ))}
        </div>
        <div className="on-sec">
          <Skeleton width={280} height={42} />
          <div className="on-g4">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} style={{ paddingTop: 20 }}>
                <Skeleton width="30%" height={14} />
                <Skeleton width="70%" height={44} style={{ marginTop: 14 }} />
              </div>
            ))}
          </div>
        </div>
      </Loading>
    </div>
  );
}
